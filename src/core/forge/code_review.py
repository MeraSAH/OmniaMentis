"""
* UBICACION: OmniaMentis/src/core/forge/code_review.py
* PROPOSITO: Motor de OmniaForge: REVISA codigo Python sin ejecutarlo (analisis
*            estatico con `ast`): errores de sintaxis, llamadas peligrosas,
*            practicas riesgosas, complejidad y metricas.
* DEPENDENCIAS: ast, re (stdlib)
* CREADO: 2026-10-20
* ESTADO: Produccion
*
* DECISION DE SEGURIDAD (2026-10-20): el servidor de OmniaMentis NUNCA ejecuta codigo
* de las personas. Un aislamiento real (contenedor/VM sin red, limites de CPU,
* memoria y tiempo) no existe en este despliegue y simularlo seria enganar. Este
* motor solo LEE el codigo: `ast.parse` no lo ejecuta ni lo importa. La ejecucion
* queda para la aplicacion de escritorio, en el equipo de la propia persona.
*
* LIMITES: 20 000 caracteres; sin bytes nulos; se atrapan RecursionError y
* MemoryError (codigo anidado a proposito). Es una ayuda de revision, no una
* garantia: que no marque nada NO significa que el codigo sea seguro.
"""

import ast
import re
from typing import Any, Dict, List, Optional, Tuple

MAX_CODE_CHARS = 20_000
MAX_FINDINGS = 30
COMPLEXITY_WARN = 10
SEVERITY_ORDER = {"alto": 0, "medio": 1, "bajo": 2}

_FENCE = re.compile(r"```[ \t]*([A-Za-z0-9_+#-]*)[ \t]*\r?\n?(.*?)```", re.S)
_SECRET_NAME = re.compile(r"(password|passwd|pwd|secret|token|api[_-]?key|apikey|clave)", re.I)

# nombre completo -> (severidad, motivo)
_RISKY: Dict[str, Tuple[str, str]] = {
    "eval": ("alto", "eval() ejecuta texto como código: si el texto viene de fuera, es ejecución remota de código."),
    "exec": ("alto", "exec() ejecuta texto como código: si el texto viene de fuera, es ejecución remota de código."),
    "compile": ("medio", "compile() prepara texto para ejecutarlo como código."),
    "__import__": ("medio", "Importación dinámica: revisa de dónde sale el nombre del módulo."),
    "os.system": ("alto", "Ejecuta comandos del sistema; con datos externos permite inyección de comandos."),
    "os.popen": ("alto", "Ejecuta comandos del sistema; con datos externos permite inyección de comandos."),
    "subprocess.run": ("medio", "Lanza procesos externos."),
    "subprocess.call": ("medio", "Lanza procesos externos."),
    "subprocess.check_call": ("medio", "Lanza procesos externos."),
    "subprocess.check_output": ("medio", "Lanza procesos externos."),
    "subprocess.Popen": ("medio", "Lanza procesos externos."),
    "pickle.load": ("alto", "pickle puede ejecutar código al leer datos no confiables."),
    "pickle.loads": ("alto", "pickle puede ejecutar código al leer datos no confiables."),
    "marshal.loads": ("alto", "marshal no es seguro con datos no confiables."),
    "yaml.load": ("alto", "yaml.load sin un Loader seguro puede ejecutar código; usa yaml.safe_load."),
    "shutil.rmtree": ("medio", "Borra carpetas completas."),
    "os.remove": ("bajo", "Borra archivos."),
    "os.unlink": ("bajo", "Borra archivos."),
    "os.rmdir": ("bajo", "Borra carpetas."),
}
_BRANCH_NODES = (ast.If, ast.For, ast.AsyncFor, ast.While, ast.ExceptHandler, ast.IfExp, ast.Assert)


class ReviewError(ValueError):
    """Entrada no valida (vacia, demasiado larga o con bytes nulos)."""


# ------------------------------------------------------------------ extraccion
def extract_code(message: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    """(lenguaje, codigo) de un mensaje con un bloque ```...```; (None, None) si no hay."""
    m = _FENCE.search(message or "")
    if not m:
        return None, None
    lang = (m.group(1) or "").lower() or None
    code = m.group(2).strip("\r\n")
    return lang, (code if code.strip() else None)


def normalize_language(lang: Optional[str]) -> Optional[str]:
    if lang in (None, "", "python", "py", "python3"):
        return "python"
    if lang in ("js", "javascript", "node", "ts", "typescript"):
        return "javascript"
    return lang


# ------------------------------------------------------------------ analisis
def _dotted(node: ast.AST) -> Optional[str]:
    parts: List[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
        return ".".join(reversed(parts))
    return None


def _complexity(fn: ast.AST) -> int:
    total = 1
    for n in ast.walk(fn):
        if isinstance(n, _BRANCH_NODES):
            total += 1
        elif isinstance(n, ast.BoolOp):
            total += len(n.values) - 1
        elif isinstance(n, ast.comprehension):
            total += 1 + len(n.ifs)
    return total


def _is_mutable_default(node: ast.AST) -> bool:
    if isinstance(node, (ast.List, ast.Dict, ast.Set)):
        return True
    return isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in {"list", "dict", "set"} and not node.args


def review(code: str) -> Dict[str, Any]:
    """Revisa codigo Python. Nunca lo ejecuta. Lanza ReviewError si la entrada no es valida."""
    if not isinstance(code, str) or not code.strip():
        raise ReviewError("No hay código para revisar.")
    if len(code) > MAX_CODE_CHARS:
        raise ReviewError(f"El código es demasiado largo (máximo {MAX_CODE_CHARS} caracteres).")
    if "\x00" in code:
        raise ReviewError("El código contiene caracteres no válidos.")
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        return {"valid": False, "error": {"line": exc.lineno or 1, "message": exc.msg or "Error de sintaxis"},
                "metrics": {"lines": len([l for l in code.splitlines() if l.strip()])}, "findings": []}
    except (RecursionError, MemoryError, ValueError, OverflowError):
        return {"valid": False, "error": {"line": 1, "message": "El código es demasiado complejo o anidado para analizarlo."},
                "metrics": {"lines": len([l for l in code.splitlines() if l.strip()])}, "findings": []}

    aliases: Dict[str, str] = {}
    imported: Dict[str, int] = {}          # nombre local -> linea
    modules = set()
    findings: List[Dict[str, Any]] = []
    functions: List[Tuple[str, int, int, bool]] = []   # nombre, linea, complejidad, tiene_docstring
    classes = 0

    def add(line: int, severity: str, kind: str, message: str) -> None:
        findings.append({"line": int(line or 0), "severity": severity, "kind": kind, "message": message})

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                local = a.asname or a.name.split(".")[0]
                aliases[local] = a.name if a.asname else a.name.split(".")[0]
                imported.setdefault(local, node.lineno)
                modules.add(a.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if mod:
                modules.add(mod.split(".")[0])
            for a in node.names:
                if a.name == "*":
                    add(node.lineno, "bajo", "import_star", f"from {mod} import * mezcla nombres sin control; importa solo lo que usas.")
                    continue
                local = a.asname or a.name
                aliases[local] = f"{mod}.{a.name}" if mod else a.name
                imported.setdefault(local, node.lineno)

    used = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            used.add(node.id)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            functions.append((node.name, node.lineno, _complexity(node), ast.get_docstring(node) is not None))
            args = node.args
            for d in list(args.defaults) + [d for d in args.kw_defaults if d is not None]:
                if _is_mutable_default(d):
                    add(d.lineno, "medio", "mutable_default",
                        f"En {node.name}(): un valor por defecto mutable se comparte entre llamadas; usa None y créalo dentro.")
        elif isinstance(node, ast.ClassDef):
            classes += 1
        elif isinstance(node, ast.ExceptHandler) and node.type is None:
            add(node.lineno, "medio", "bare_except", "except: sin tipo captura todo (incluso Ctrl+C); indica la excepción esperada.")
        elif isinstance(node, ast.Compare):
            for op, right in zip(node.ops, node.comparators):
                if isinstance(op, (ast.Eq, ast.NotEq)) and isinstance(right, ast.Constant) and right.value is None:
                    add(node.lineno, "bajo", "compare_none", "Compara con None usando `is` / `is not`, no `==` / `!=`.")
        elif isinstance(node, ast.Assign):
            if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str) and len(node.value.value) >= 6:
                for t in node.targets:
                    name = t.id if isinstance(t, ast.Name) else (t.attr if isinstance(t, ast.Attribute) else "")
                    if name and _SECRET_NAME.search(name):
                        add(node.lineno, "alto", "hardcoded_secret",
                            f"Posible secreto escrito en el código ({name}); guárdalo en una variable de entorno, no en el repositorio.")
        elif isinstance(node, ast.Call):
            dotted = _dotted(node.func)
            if dotted:
                head, _, rest = dotted.partition(".")
                full = aliases.get(head, head) + (("." + rest) if rest else "")
                safe_yaml = full == "yaml.load" and any(
                    kw.arg == "Loader" and (_dotted(kw.value) or "").split(".")[-1] in {"SafeLoader", "CSafeLoader"}
                    for kw in node.keywords)
                if full in _RISKY and not safe_yaml:
                    sev, why = _RISKY[full]
                    add(node.lineno, sev, "risky_call", f"{full}(): {why}")
                if full.startswith("subprocess.") or full in {"os.system", "os.popen"}:
                    for kw in node.keywords:
                        if kw.arg == "shell" and isinstance(kw.value, ast.Constant) and kw.value.value is True:
                            add(node.lineno, "alto", "shell_true", "shell=True pasa el comando por la shell: con datos externos permite inyección de comandos.")
                if full in {"requests.get", "requests.post", "requests.put", "requests.delete", "requests.request"}:
                    for kw in node.keywords:
                        if kw.arg == "verify" and isinstance(kw.value, ast.Constant) and kw.value.value is False:
                            add(node.lineno, "alto", "tls_off", "verify=False desactiva la comprobación del certificado TLS.")
                if full == "open" and len(node.args) >= 2 and isinstance(node.args[1], ast.Constant) \
                        and isinstance(node.args[1].value, str) and set(node.args[1].value) & set("wax+"):
                    add(node.lineno, "bajo", "writes_file", "Escribe en un archivo: confirma que la ruta no depende de datos externos.")

    for local, line in imported.items():
        if local not in used:
            add(line, "bajo", "unused_import", f"Posible import sin usar: {local}.")

    for name, line, cx, _doc in functions:
        if cx >= COMPLEXITY_WARN:
            add(line, "medio", "complex_function", f"{name}() tiene complejidad {cx} (≥ {COMPLEXITY_WARN}); considera dividirla.")

    findings.sort(key=lambda f: (SEVERITY_ORDER[f["severity"]], f["line"]))
    total = len(findings)
    return {
        "valid": True,
        "metrics": {
            "lines": len([l for l in code.splitlines() if l.strip()]),
            "functions": len(functions), "classes": classes,
            "functions_without_docstring": sum(1 for f in functions if not f[3]),
            "max_complexity": max((f[2] for f in functions), default=0),
            "imports": sorted(modules),
        },
        "findings": findings[:MAX_FINDINGS],
        "findings_total": total,
    }


def summary(result: Dict[str, Any]) -> Dict[str, Any]:
    """Resumen NUMÉRICO de una revisión, para guardar y graficar. Nunca incluye el código."""
    sev = {"alto": 0, "medio": 0, "bajo": 0}
    for f in result.get("findings") or []:
        if f.get("severity") in sev:
            sev[f["severity"]] += 1
    m = result.get("metrics") or {}
    return {"valid": bool(result.get("valid")), "findings": int(result.get("findings_total", 0)), "sev": sev,
            "lines": int(m.get("lines", 0)), "max_complexity": int(m.get("max_complexity", 0))}


def format_review(result: Dict[str, Any]) -> str:
    if not result.get("valid"):
        e = result["error"]
        return f"El código no es Python válido: línea {e['line']}: {e['message']}."
    m = result["metrics"]
    lines = [f"Revisión estática (no ejecuté nada): {m['lines']} líneas, {m['functions']} función(es), {m['classes']} clase(s); "
             f"complejidad máxima {m['max_complexity']}."]
    if m["imports"]:
        lines.append("Importa: " + ", ".join(m["imports"]) + ".")
    if m["functions_without_docstring"]:
        lines.append(f"{m['functions_without_docstring']} función(es) sin docstring.")
    f = result["findings"]
    if not f:
        lines.append("No marqué nada con las reglas que tengo. Eso no garantiza que sea seguro.")
    else:
        lines.append(f"Hallazgos ({result['findings_total']}):")
        for x in f:
            lines.append(f"  • [{x['severity']}] línea {x['line']}: {x['message']}")
        if result["findings_total"] > len(f):
            lines.append(f"  … y {result['findings_total'] - len(f)} más.")
    return "\n".join(lines)
