"""
* UBICACION: OmniaMentis/src/core/focus/focus.py
* PROPOSITO: Motor de OmniaChronos: interpretacion de ordenes de bloques de enfoque
*            y calculo de tiempos. Funciones puras (sin E/S).
* DEPENDENCIAS: stdlib
* CREADO: 2026-10-18
* ESTADO: Produccion
*
* ALCANCE: el servidor guarda y calcula los bloques. Bloquear notificaciones y
*   poner la pantalla en "enfoque absoluto" lo hace la interfaz (el widget
*   `focus_timer` trae los datos). El servidor no puede bloquear nada en el
*   dispositivo y no lo promete.
"""

import re
from typing import Dict, Optional

from core.habits.habits import normalize

MIN_MINUTES = 5
MAX_MINUTES = 180
DEFAULT_MINUTES = 25

_MINUTES = re.compile(r"\b(\d{1,4})\s*(?:min|mins|minutos?)\b")
_END = re.compile(r"\b(termine|termino|acabe|finalice|finalizar|detener|detengo|parar|pare|cancelar|cancelo|stop)\b")
_STATUS = re.compile(r"\b(cuanto|cuantos|mis bloques|resumen|estadisticas|he enfocado|tiempo enfocado|bloque actual|como va)\b")
_LABELS = {"evolucion cognitiva": "Evolución Cognitiva", "reset dopaminico": "Reset Dopamínico"}


def parse_minutes(message: str) -> Optional[int]:
    """Minutos pedidos en el texto, o None si no los indica."""
    m = _MINUTES.search(normalize(message))
    return int(m.group(1)) if m else None


def valid_minutes(minutes: int) -> bool:
    return isinstance(minutes, int) and MIN_MINUTES <= minutes <= MAX_MINUTES


def detect_intent(message: str) -> str:
    """'end', 'status' o 'start'."""
    norm = normalize(message)
    if _END.search(norm):
        return "end"
    if _STATUS.search(norm):
        return "status"
    return "start"


def detect_label(message: str) -> Optional[str]:
    norm = normalize(message)
    for key, label in _LABELS.items():
        if key in norm:
            return label
    return None


def remaining_seconds(started_at: float, minutes: int, now: float) -> int:
    return max(0, int(round(started_at + minutes * 60 - now)))


def elapsed_minutes(started_at: float, minutes: int, now: float) -> float:
    """Minutos transcurridos, nunca mas que lo planeado ni menos que 0."""
    raw = (now - started_at) / 60.0
    return round(max(0.0, min(raw, float(minutes))), 1)


def summarize_day(ends: list, day: str, day_of) -> Dict:
    """Suma los bloques terminados de `day`. `ends` = payloads de focus_end con
    started_at y elapsed_min; `day_of(ts)` convierte un instante a fecha local."""
    total, blocks = 0.0, 0
    for e in ends:
        try:
            if day_of(float(e["started_at"])) == day:
                total += float(e["elapsed_min"])
                blocks += 1
        except (KeyError, TypeError, ValueError):
            continue
    return {"minutes": round(total, 1), "blocks": blocks}
