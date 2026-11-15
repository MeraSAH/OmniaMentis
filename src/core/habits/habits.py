"""
* UBICACION: OmniaMentis/src/core/habits/habits.py
* PROPOSITO: Motor de OmniaHabits: catalogo de habitos, puntos con multiplicador,
*            progreso del dia y racha. Funciones puras (sin E/S): el modulo solo
*            presenta lo que calcula el motor.
* DEPENDENCIAS: stdlib
* CREADO: 2026-10-18
* ESTADO: Produccion
*
* DECISIONES
*   - Catalogo fijo con los 9 habitos del documento de arquitectura y sus
*     multiplicadores (maxima x3, alta x2, media/baja x1). Habitos propios del
*     usuario quedan para una version posterior.
*   - Puntos = BASE_POINTS (10) x multiplicador. Maximo diario = 160. Los numeros
*     69/201/25.5 % del documento eran un ejemplo de pantalla, no una regla.
*   - Colores: el documento nombra el color de 5 habitos sin dar el hexadecimal;
*     los hex son decision de implementacion. Los 4 habitos sin color en el
*     documento reciben uno propio (marcados "assigned": True).
*   - Un habito se marca una sola vez por dia.
*   - El dia se calcula en la zona horaria de Ecuador (OMNIA_TZ lo cambia).
"""

import re
import unicodedata
from datetime import date, datetime, timedelta, timezone
from typing import Dict, Iterable, List, Optional, Set

try:  # zoneinfo necesita datos de zona horaria; en Windows puede faltar "tzdata"
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    ZoneInfo = None

BASE_POINTS = 10
DEFAULT_TZ = "America/Guayaquil"
_FALLBACK_TZ = timezone(timedelta(hours=-5))  # Ecuador continental, sin horario de verano

HABITS: List[Dict] = [
    {"id": "victoria_magistral", "name": "Victoria Magistral 6:00 AM", "multiplier": 3,
     "color_name": "Rojo Carmesí", "color_hex": "#DC143C", "assigned": False,
     "aliases": ["victoria magistral"]},
    {"id": "ducha_choque", "name": "Ducha de Choque Térmico", "multiplier": 3,
     "color_name": "Cian Glacial", "color_hex": "#00E5FF", "assigned": True,
     "aliases": ["ducha de choque", "ducha fria", "ducha helada"]},
    {"id": "entrenamiento_elite", "name": "Entrenamiento de Élite", "multiplier": 2,
     "color_name": "Naranja Fuego", "color_hex": "#FF4500", "assigned": False,
     "aliases": ["entrenamiento de elite"]},
    {"id": "reset_dopaminico", "name": "Reset Dopamínico", "multiplier": 2,
     "color_name": "Morado Profundo", "color_hex": "#4B0082", "assigned": False,
     "aliases": ["reset dopaminico"]},
    {"id": "desintoxicacion_digital", "name": "Desintoxicación Digital", "multiplier": 2,
     "color_name": "Amarillo Neón", "color_hex": "#FFFF33", "assigned": False,
     "aliases": ["desintoxicacion digital"]},
    {"id": "evolucion_cognitiva", "name": "Evolución Cognitiva", "multiplier": 1,
     "color_name": "Azul Eléctrico", "color_hex": "#0A7CFF", "assigned": False,
     "aliases": ["evolucion cognitiva"]},
    {"id": "auditoria_tiempo", "name": "Auditoría de Tiempo", "multiplier": 1,
     "color_name": "Azul Cielo", "color_hex": "#87CEEB", "assigned": False,
     "aliases": ["auditoria de tiempo"]},
    {"id": "estado_sobriedad", "name": "Estado de Sobriedad", "multiplier": 1,
     "color_name": "Verde Esmeralda", "color_hex": "#2ECC71", "assigned": True,
     "aliases": ["estado de sobriedad", "sobriedad"]},
    {"id": "bitacora_objetivos", "name": "Bitácora de Objetivos", "multiplier": 1,
     "color_name": "Blanco Hielo", "color_hex": "#E8F4FF", "assigned": True,
     "aliases": ["bitacora de objetivos"]},
]
_BY_ID = {h["id"]: h for h in HABITS}

_COMPLETION = re.compile(
    r"\b(complete|completado|completada|hice|cumpli|termine|marque|checkee|check|logre|realice)\b")
_STATUS = re.compile(r"\b(racha|puntos|progreso|avance|como voy|mis habitos|resumen)\b")


def normalize(text: str) -> str:
    """Minusculas y sin tildes, para comparar de forma tolerante."""
    decomposed = unicodedata.normalize("NFD", (text or "").lower())
    return "".join(c for c in decomposed if unicodedata.category(c) != "Mn")


def points_for(habit_id: str) -> int:
    return BASE_POINTS * _BY_ID[habit_id]["multiplier"]


def max_daily_points() -> int:
    return sum(points_for(h["id"]) for h in HABITS)


def get_habit(habit_id: str) -> Optional[Dict]:
    return _BY_ID.get(habit_id)


def find_habit(message: str) -> Optional[Dict]:
    """Habito mencionado en el texto (coincidencia mas larga). None si no hay."""
    norm = normalize(message)
    best, best_len = None, 0
    for h in HABITS:
        for alias in h["aliases"]:
            if alias in norm and len(alias) > best_len:
                best, best_len = h, len(alias)
    return best


def is_completion(message: str) -> bool:
    return bool(_COMPLETION.search(normalize(message)))


def is_status_request(message: str) -> bool:
    return bool(_STATUS.search(normalize(message)))


def _tz():
    import os
    name = os.environ.get("OMNIA_TZ", DEFAULT_TZ)
    if ZoneInfo is not None:
        try:
            return ZoneInfo(name)
        except Exception:
            pass
    return _FALLBACK_TZ


def day_key(ts: float) -> str:
    """Fecha local (YYYY-MM-DD) de un instante, en la zona horaria configurada."""
    return datetime.fromtimestamp(ts, tz=_tz()).date().isoformat()


def progress(done_ids: Iterable[str]) -> Dict:
    """Puntos del dia. Ignora ids desconocidos y repetidos."""
    ids: Set[str] = {i for i in done_ids if i in _BY_ID}
    obtained = sum(points_for(i) for i in ids)
    possible = max_daily_points()
    return {"obtained": obtained, "remaining": possible - obtained, "possible": possible,
            "percent": round(100.0 * obtained / possible, 1), "done": len(ids), "total": len(HABITS)}


def streak(days: Iterable[str], today: str) -> int:
    """Dias consecutivos con al menos un habito. Si hoy aun no hay registro, la
    racha cuenta desde ayer (todavia no se rompe). Fechas invalidas se ignoran."""
    valid: Set[date] = set()
    for d in days:
        try:
            valid.add(date.fromisoformat(d))
        except (TypeError, ValueError):
            continue
    try:
        cursor = date.fromisoformat(today)
    except (TypeError, ValueError):
        return 0
    if cursor not in valid:
        cursor -= timedelta(days=1)
    count = 0
    while cursor in valid:
        count += 1
        cursor -= timedelta(days=1)
    return count
