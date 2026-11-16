"""
* UBICACIÓN: OmniaMentis/src/router/slash.py
* PROPÓSITO: Comandos «/» del desarrollador para enviar información directamente a un módulo, sin pasar por la
*            puntuación del router. Funciones puras (sin E/S). QUIÉN puede usarlos lo decide main_flask.py;
*            QUÉ módulos puede alcanzar lo sigue decidiendo el router (edad + autorización elevada).
* CREADO: 2026-11-16
* ESTADO: Producción
*
* FORMATO:
*   /                              → lista los módulos y el formato
*   /[Nombre del módulo] mensaje   → entrega «mensaje» a ese módulo
*   Ejemplo: /[Corporal Verified] hueso púbico 15.2
"""

import re
from dataclasses import dataclass
from typing import List, Optional

_CMD = re.compile(r"^\s*/\[\s*([^\]\n]{1,60}?)\s*\]\s*(.*)$", re.S)
_LIST = re.compile(r"^\s*/\s*$")

FORMAT_HELP = "/[Nombre del módulo] mensaje      Ejemplo: /[Corporal Verified] hueso púbico 15.2"


@dataclass(frozen=True)
class SlashCommand:
    kind: str                     # "list" | "module"
    module: str = ""
    text: str = ""


def is_slash(message: str) -> bool:
    return isinstance(message, str) and message.lstrip().startswith("/")


def parse(message: str) -> Optional[SlashCommand]:
    """None si el mensaje no empieza por «/». Un «/» que no cumple el formato devuelve kind='list' para mostrar
    la ayuda en vez de mandar el texto a la conversación."""
    if not is_slash(message):
        return None
    if _LIST.match(message):
        return SlashCommand("list")
    m = _CMD.match(message)
    if not m:
        return SlashCommand("list")
    return SlashCommand("module", module=m.group(1), text=m.group(2).strip())


def resolve_module(name: str, available: List[str]) -> Optional[str]:
    """Nombre exacto del módulo (sin distinguir mayúsculas ni espacios de más), o None."""
    wanted = " ".join(name.split()).casefold()
    for real in available:
        if real.casefold() == wanted:
            return real
    return None


def help_text(available: List[str]) -> str:
    lines = ["Comandos de desarrollador:", FORMAT_HELP, "", "Módulos disponibles:"]
    lines += [f"  /[{n}]" for n in available]
    return "\n".join(lines)
