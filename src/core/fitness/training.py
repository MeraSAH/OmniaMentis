"""
* UBICACION: OmniaMentis/src/core/fitness/training.py
* PROPOSITO: Motor de entrenamiento de OmniaAthletics: arma rutinas de fuerza /
*            resistencia con reglas fijas y resume el entrenamiento semanal.
*            El modulo solo presenta lo que este motor calcula.
* DEPENDENCIAS: re (stdlib)
* CREADO: 2026-10-18
* ESTADO: Produccion
*
* DECISIONES (tomadas por el motor, no por el modulo)
*   - Todo es determinista y sin datos medicos: no diagnostica ni prescribe.
*   - Menores (13-17): maximo 4 dias por semana, nunca mas de 3 series, nunca menos
*     de 8 repeticiones (sin trabajo de fuerza maxima), nivel tope "intermedio",
*     tecnica antes que carga y supervision de un adulto/entrenador.
*   - El modulo no da metas de deficit calorico ni de bajar de peso: eso lo
*     decide NutriVida y, para menores, jamas.
*   - Las recomendaciones de actividad (OMS: adultos >=150 min/semana moderada;
*     13-17 anos, promedio de 60 min/dia) son referencia general, no una pauta medica.
"""

import re
from typing import Dict, Iterable, List, Optional, Tuple

ADULT = "adult"
MIN_DAYS, MAX_DAYS, MAX_DAYS_MINOR = 2, 6, 4
LEVELS = ("principiante", "intermedio", "avanzado")
GOALS = ("salud", "fuerza", "masa", "resistencia")
PLACES = ("casa", "gimnasio")
DEFAULTS = {"days": 3, "level": "principiante", "goal": "salud", "place": "casa"}
MIN_SESSION_MIN, MAX_SESSION_MIN = 5, 300
WEEK_SECONDS = 7 * 24 * 3600

_DAYS = re.compile(r"(\d)\s*(?:d[ií]as?|veces\s+(?:a\s+la|por)\s+semana)", re.I)
_LEVEL = (
    ("avanzado", re.compile(r"\bavanzad[oa]\b", re.I)),
    ("intermedio", re.compile(r"\bintermedi[oa]\b", re.I)),
    ("principiante", re.compile(r"\b(principiante|novato|novata|empiezo|empezando|primera vez)\b", re.I)),
)
_GOAL = (
    ("fuerza", re.compile(r"\bfuerza\b", re.I)),
    ("masa", re.compile(r"\b(masa|m[uú]sculo|hipertrofia|volumen)\b", re.I)),
    ("resistencia", re.compile(r"\b(resistencia|cardio|correr|running|aer[oó]bico)\b", re.I)),
    ("salud", re.compile(r"\b(salud|bienestar|mantenerme|general)\b", re.I)),
)
_HOME = re.compile(r"en casa|sin equipo|sin pesas|sin gimnasio|calistenia|peso corporal", re.I)
_GYM = re.compile(r"gimnasio|\bgym\b|pesas|mancuernas|m[aá]quinas", re.I)
_MINUTES = re.compile(r"(\d{1,3})\s*(?:min(?:utos?)?|mins?)\b", re.I)
_HOURS = re.compile(r"(\d{1,2}(?:[.,]\d)?)\s*(?:h|horas?)\b", re.I)
_LEAN = re.compile(r"definici[oó]n|definir|marcar (?:los )?abdominales|bajar grasa|bajar de peso|adelgazar|"
                   r"perder peso|d[eé]ficit|quemar grasa|bajar kilos", re.I)


class InvalidRequest(ValueError):
    """Pedido de rutina o de registro con datos fuera de rango."""


# ------------------------------------------------------------------ lectura del mensaje
def parse_request(message: Optional[str]) -> Dict[str, object]:
    """Saca dias, nivel, objetivo y lugar de un texto libre. Solo devuelve lo que encuentra."""
    text = message or ""
    out: Dict[str, object] = {}
    m = _DAYS.search(text)
    if m:
        out["days"] = int(m.group(1))
    for name, rx in _LEVEL:
        if rx.search(text):
            out["level"] = name
            break
    for name, rx in _GOAL:
        if rx.search(text):
            out["goal"] = name
            break
    if _HOME.search(text):
        out["place"] = "casa"
    elif _GYM.search(text):
        out["place"] = "gimnasio"
    return out


def wants_fat_loss(message: Optional[str]) -> bool:
    return bool(_LEAN.search(message or ""))


def parse_minutes(message: Optional[str]) -> Optional[float]:
    """Duracion del entrenamiento mencionada en el texto (minutos) o None."""
    text = message or ""
    m = _MINUTES.search(text)
    if m:
        return float(m.group(1))
    h = _HOURS.search(text)
    if h:
        return round(float(h.group(1).replace(",", ".")) * 60, 1)
    return None


def valid_minutes(minutes: object) -> bool:
    return (isinstance(minutes, (int, float)) and not isinstance(minutes, bool)
            and MIN_SESSION_MIN <= minutes <= MAX_SESSION_MIN)


# ------------------------------------------------------------------ catalogo
_EX = {
    "rodilla":    {"casa": "Sentadilla con peso corporal", "gimnasio": "Sentadilla goblet con mancuerna"},
    "bisagra":    {"casa": "Puente de glúteos", "gimnasio": "Peso muerto rumano con mancuernas"},
    "unilateral": {"casa": "Zancadas alternas", "gimnasio": "Zancadas con mancuernas"},
    "empuje_h":   {"casa": "Flexiones de brazos (apoya las rodillas si hace falta)", "gimnasio": "Press de pecho con mancuernas"},
    "empuje_v":   {"casa": "Flexión en V (pike push-up)", "gimnasio": "Press de hombros con mancuernas"},
    "tiron_h":    {"casa": "Remo invertido bajo una mesa firme", "gimnasio": "Remo con mancuerna a una mano"},
    "tiron_v":    {"casa": "Remo inclinado con mochila cargada", "gimnasio": "Jalón al pecho en polea"},
    "triceps":    {"casa": "Flexiones con manos juntas", "gimnasio": "Extensión de tríceps con mancuerna"},
    "biceps":     {"casa": "Curl con mochila cargada", "gimnasio": "Curl de bíceps con mancuernas"},
    "gemelos":    {"casa": "Elevación de talones", "gimnasio": "Elevación de talones con mancuernas"},
    "core":       {"casa": "Plancha frontal", "gimnasio": "Plancha frontal"},
}
_TIMED = {"core": "20-40 s"}            # patrones que se miden en segundos
_FIXED_REPS = {"gemelos": "12-15"}

_FB_A = ["rodilla", "empuje_h", "tiron_h", "core"]
_FB_B = ["bisagra", "empuje_v", "tiron_v", "unilateral"]
_UPPER = ["empuje_h", "tiron_h", "empuje_v", "tiron_v", "biceps"]
_LOWER = ["rodilla", "bisagra", "unilateral", "gemelos", "core"]
_PUSH = ["empuje_h", "empuje_v", "triceps", "core"]
_PULL = ["tiron_h", "tiron_v", "biceps"]
_LEGS = ["rodilla", "bisagra", "unilateral", "gemelos"]

# (series, repeticiones, descanso en segundos)
_TABLE: Dict[Tuple[str, str], Tuple[int, str, int]] = {
    ("principiante", "salud"): (2, "10-12", 60), ("principiante", "masa"): (3, "10-12", 75),
    ("principiante", "fuerza"): (3, "8-10", 120), ("principiante", "resistencia"): (2, "15-20", 45),
    ("intermedio", "salud"): (3, "10-12", 60), ("intermedio", "masa"): (3, "8-12", 90),
    ("intermedio", "fuerza"): (4, "5-8", 150), ("intermedio", "resistencia"): (3, "15-20", 45),
    ("avanzado", "salud"): (3, "8-12", 60), ("avanzado", "masa"): (4, "6-12", 90),
    ("avanzado", "fuerza"): (5, "3-6", 180), ("avanzado", "resistencia"): (3, "15-25", 40),
}


def _plan_for_days(days: int, goal: str) -> List[Tuple[str, List[str]]]:
    """Plantilla de sesiones: lista de (nombre, patrones)."""
    if goal == "resistencia":
        plan: List[Tuple[str, List[str]]] = []
        fb = [("Cuerpo completo A (ligero)", _FB_A), ("Cuerpo completo B (ligero)", _FB_B)]
        for i in range(days):
            plan.append(("Cardio en zona 2", ["cardio"]) if i % 2 == 0 else fb[(i // 2) % 2])
        return plan
    if days == 2:
        return [("Cuerpo completo A", _FB_A), ("Cuerpo completo B", _FB_B)]
    if days == 3:
        return [("Cuerpo completo A", _FB_A), ("Cuerpo completo B", _FB_B), ("Cuerpo completo A", _FB_A)]
    if days == 4:
        return [("Tren superior", _UPPER), ("Tren inferior", _LOWER), ("Tren superior", _UPPER), ("Tren inferior", _LOWER)]
    if days == 5:
        return [("Tren superior", _UPPER), ("Tren inferior", _LOWER), ("Empuje", _PUSH), ("Tirón", _PULL), ("Piernas", _LEGS)]
    return [("Empuje", _PUSH), ("Tirón", _PULL), ("Piernas", _LEGS), ("Empuje", _PUSH), ("Tirón", _PULL), ("Piernas", _LEGS)]


def _reps_bounds(reps: str) -> Tuple[int, int]:
    lo, hi = reps.split("-")
    return int(lo), int(hi)


def build_routine(age_band: str, days: Optional[int] = None, level: Optional[str] = None,
                  goal: Optional[str] = None, place: Optional[str] = None) -> Dict[str, object]:
    """Rutina semanal. Aplica los limites de edad (ver DECISIONES) y registra en
    `assumed` lo que se completo por defecto y en `adjusted` lo que se limito."""
    minor = age_band != ADULT
    assumed: List[str] = []
    adjusted: List[str] = []

    if days is None:
        days = DEFAULTS["days"]; assumed.append(f"{days} días por semana")
    if isinstance(days, bool) or not isinstance(days, int) or not (MIN_DAYS <= days <= MAX_DAYS):
        raise InvalidRequest(f"Elige entre {MIN_DAYS} y {MAX_DAYS} días de entrenamiento por semana.")
    if level is None:
        level = DEFAULTS["level"]; assumed.append(f"nivel {level}")
    if goal is None:
        goal = DEFAULTS["goal"]; assumed.append("objetivo de salud general")
    if place is None:
        place = DEFAULTS["place"]; assumed.append("entrenando en casa, sin equipo")
    if level not in LEVELS or goal not in GOALS or place not in PLACES:
        raise InvalidRequest("Nivel, objetivo o lugar no válidos.")

    if minor:
        if days > MAX_DAYS_MINOR:
            days = MAX_DAYS_MINOR; adjusted.append(f"a tu edad el máximo recomendado son {MAX_DAYS_MINOR} días por semana")
        if level == "avanzado":
            level = "intermedio"; adjusted.append("nivel limitado a intermedio")

    sets, reps, rest = _TABLE[(level, goal)]
    if minor:
        sets = min(sets, 3)
        lo, hi = _reps_bounds(reps)
        if lo < 8:
            reps = "8-12"
            adjusted.append("repeticiones entre 8 y 12: sin trabajo de fuerza máxima")
        rest = min(rest, 90)

    sessions = []
    for name, patterns in _plan_for_days(days, goal):
        exercises = []
        for pat in patterns:
            if pat == "cardio":
                exercises.append({"name": "Caminata rápida o trote suave (puedes hablar sin ahogarte)",
                                  "sets": 1, "reps": "25-40 min" if not minor else "20-40 min", "rest_s": 0})
                continue
            exercises.append({
                "name": _EX[pat][place], "sets": sets,
                "reps": _TIMED.get(pat) or _FIXED_REPS.get(pat) or reps,
                "rest_s": rest})
        sessions.append({"name": name, "exercises": exercises})
    return {"days": days, "level": level, "goal": goal, "place": place,
            "sessions": sessions, "assumed": assumed, "adjusted": adjusted, "minor": minor}


def routine_notes(minor: bool) -> List[str]:
    notes = [
        "Calienta 5-8 minutos (movilidad articular y series ligeras) y termina estirando suave.",
        "Progresión: sube primero las repeticiones; cuando llegues al máximo del rango en todas las series con buena técnica, aumenta un poco la carga o la dificultad.",
        "Descansa al menos un día entre sesiones de la misma zona. Si algo duele (no es cansancio), para y consulta a un profesional.",
        "Es una guía general, no una valoración médica: si tienes una lesión o condición de salud, consúltalo antes de empezar.",
    ]
    if minor:
        notes.insert(1, "A tu edad la técnica va antes que el peso: entrena con supervisión de un adulto o entrenador y no levantes al máximo.")
    return notes


def format_routine(r: Dict[str, object]) -> str:
    lines = [f"Rutina de {r['days']} días · nivel {r['level']} · objetivo {r['goal']} · {'en casa' if r['place'] == 'casa' else 'en gimnasio'}"]
    for i, s in enumerate(r["sessions"], 1):
        lines.append(f"\nDía {i} · {s['name']}")
        for e in s["exercises"]:
            if e["sets"] == 1 and e["rest_s"] == 0:
                lines.append(f"  • {e['name']}: {e['reps']}")
            else:
                lines.append(f"  • {e['name']}: {e['sets']} × {e['reps']} (descanso {e['rest_s']} s)")
    return "\n".join(lines)


# ------------------------------------------------------------------ registro y resumen
def summarize_week(records: Iterable[Dict[str, object]], now: float) -> Dict[str, object]:
    """Sesiones y minutos de los ultimos 7 dias. Ignora registros rotos."""
    sessions, minutes = 0, 0.0
    for r in records or []:
        try:
            created = float(r["created_at"])
            m = float((r.get("payload") or {})["minutes"])
        except (KeyError, TypeError, ValueError):
            continue
        if now - WEEK_SECONDS <= created <= now + 60 and valid_minutes(m):
            sessions += 1
            minutes += m
    return {"sessions": sessions, "minutes": round(minutes, 1)}


def activity_reference(age_band: str) -> str:
    if age_band == ADULT:
        return "Referencia general (OMS): al menos 150 minutos de actividad moderada por semana."
    return "Referencia general (OMS) para tu edad: unos 60 minutos de actividad al día en promedio."
