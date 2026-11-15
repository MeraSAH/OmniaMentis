#!/usr/bin/env python3
"""
* UBICACIÓN: OmniaMentis/scripts/fons_operator.py
* PROPÓSITO: Administra los REVISORES con nombre del panel del Fons: agrega,
*            lista y retira personas, cada una con su propia contraseña. Escribe
*            la variable FONS_OPERATORS del archivo .env (sin tocar el resto).
* DEPENDENCIAS: getpass, secrets (stdlib), src/core/auth/fons_auth.py
* CREADO: 2026-10-20
* ESTADO: Producción
*
* USO (PowerShell, con el entorno virtual activo y PYTHONPATH=src):
*     python scripts\\fons_operator.py add ana        # pide la contraseña de ana
*     python scripts\\fons_operator.py list
*     python scripts\\fons_operator.py remove ana     # pierde el acceso al reiniciar el servidor
*
* NOTA: cada decisión queda en data/fons_audit.jsonl con el nombre del revisor.
* Reinicia el servidor después de cambiar el .env (lo lee al arrancar).
"""

import argparse
import getpass
import secrets
import sys
from pathlib import Path
from typing import Dict, List

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from core.auth.fons_auth import hash_password, parse_operators, OPERATOR_RE, LEGACY_OPERATOR  # noqa: E402

ENV_FILE = PROJECT_ROOT / ".env"
KEY = "FONS_OPERATORS"
MIN_PASSWORD = 10


def read_env(path: Path) -> List[str]:
    if not path.exists():
        return []
    return [ln.rstrip("\n") for ln in path.read_text(encoding="utf-8").splitlines()]


def get_value(lines: List[str], key: str) -> str:
    prefix = f"{key}="
    for ln in lines:
        if ln.strip().startswith(prefix):
            return ln.strip()[len(prefix):]
    return ""


def upsert(lines: List[str], key: str, value: str) -> List[str]:
    new_line, prefix = f"{key}={value}", f"{key}="
    for i, ln in enumerate(lines):
        if ln.strip().startswith(prefix):
            lines[i] = new_line
            return lines
    lines.append(new_line)
    return lines


def serialize(ops: Dict[str, str]) -> str:
    return ",".join(f"{name}:{h}" for name, h in ops.items())


def add_operator(lines: List[str], name: str, password: str) -> List[str]:
    if name == LEGACY_OPERATOR or not OPERATOR_RE.match(name):
        raise ValueError("El nombre debe ir en minúsculas (letras, números, - o _), de 2 a 32 caracteres, "
                         f"empezar con letra y no ser '{LEGACY_OPERATOR}'.")
    if len(password) < MIN_PASSWORD:
        raise ValueError(f"La contraseña debe tener al menos {MIN_PASSWORD} caracteres.")
    ops = parse_operators(get_value(lines, KEY))
    ops[name] = hash_password(password)          # si ya existía, se cambia su contraseña
    lines = upsert(lines, KEY, serialize(ops))
    if not get_value(lines, "FONS_SECRET_KEY"):  # la clave de firma se crea una vez; no se rota
        lines = upsert(lines, "FONS_SECRET_KEY", secrets.token_hex(32))
    return lines


def remove_operator(lines: List[str], name: str) -> List[str]:
    ops = parse_operators(get_value(lines, KEY))
    if name not in ops:
        raise ValueError(f"No existe el revisor '{name}'.")
    del ops[name]
    return upsert(lines, KEY, serialize(ops))


def write_env(path: Path, lines: List[str]) -> None:
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Revisores con nombre del panel del Fons")
    ap.add_argument("action", choices=["add", "list", "remove"])
    ap.add_argument("name", nargs="?")
    args = ap.parse_args(argv)
    lines = read_env(ENV_FILE)
    try:
        if args.action == "list":
            ops = parse_operators(get_value(lines, KEY))
            print("Revisores con nombre:", ", ".join(ops) if ops else "(ninguno)")
            if get_value(lines, "FONS_PASSWORD_HASH"):
                print(f"Modo anterior activo: revisor '{LEGACY_OPERATOR}' (FONS_PASSWORD_HASH).")
            return 0
        if not args.name:
            print("Falta el nombre del revisor.")
            return 2
        if args.action == "add":
            pw = getpass.getpass(f"Contraseña para {args.name}: ")
            if pw != getpass.getpass("Confirmar contraseña: "):
                print("Las contraseñas no coinciden.")
                return 1
            lines = add_operator(lines, args.name, pw)
        else:
            lines = remove_operator(lines, args.name)
    except ValueError as exc:
        print(f"Error: {exc}")
        return 1
    except (EOFError, KeyboardInterrupt):
        print("\nOperación cancelada.")
        return 1
    write_env(ENV_FILE, lines)
    print(f"Listo. .env actualizado: {ENV_FILE}\nReinicia el servidor para aplicar el cambio.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
