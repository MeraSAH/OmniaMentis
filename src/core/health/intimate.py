"""
* UBICACIÓN: OmniaMentis/src/core/health/intimate.py
* PROPÓSITO: Medida corporal íntima (opcional) de Corporal: de dónde sale la medida y cuántos cm. Funciones
*            puras (sin E/S). SOLO adultos verificados con consentimiento expreso: quien llame debe comprobarlo
*            (el módulo Corporal y la API lo hacen). No compara, no califica y no da rangos «normales».
* CREADO: 2026-11-16
* ESTADO: Producción
*
* ORÍGENES (de dónde se mide):
*   hueso_pubico   longitud desde el hueso púbico (presionando) hasta la punta
*   base           longitud desde la base visible, sin presionar, hasta la punta
*   perimetro      perímetro (circunferencia) a media altura
"""

import re
from typing import Dict, Optional, Tuple

from core.health.nutrition import InvalidMeasure

ORIGINS = {
    "hueso_pubico": {"label": "Longitud desde el hueso púbico", "tipo": "longitud", "range": (3.0, 30.0)},
    "base": {"label": "Longitud desde la base", "tipo": "longitud", "range": (3.0, 30.0)},
    "perimetro": {"label": "Perímetro a media altura", "tipo": "perimetro", "range": (5.0, 25.0)},
}

_NUM = re.compile(r"(?<![\d.,])(\d{1,2}(?:[.,]\d{1,2})?)\s*(?:cm|cent[ií]metros?)?(?![\d.,])", re.I)
_ORIGIN_RX = (
    ("hueso_pubico", re.compile(r"hueso\s*p[uú]bico|\bbpel\b|\bpubis\b", re.I)),
    ("perimetro", re.compile(r"per[ií]metro|circunferencia|grosor", re.I)),
    ("base", re.compile(r"\bnbp\b|\bbase\b|desde\s+la\s+base", re.I)),
)
# Palabras de otras medidas corporales: si aparecen, el mensaje NO es de esta función (va a NutriVida).
_OTHER_BODY = re.compile(r"cuello|cintura|cadera|brazo|b[ií]ceps|pantorrilla|grasa|peso|altura|estatura|mido\s+\d{3}", re.I)
_INTIMATE_WORD = re.compile(r"[ií]ntima|miembro|peneana|pene\b", re.I)


def parse_message(message: str) -> Tuple[Optional[str], Optional[float]]:
    """(origen, cm) encontrados en un texto libre; None en lo que falte. Si el texto habla de otras medidas
    del cuerpo, devuelve (None, None)."""
    text = message or ""
    if _OTHER_BODY.search(text):
        return None, None
    origin = next((key for key, rx in _ORIGIN_RX if rx.search(text)), None)
    m = _NUM.search(text)
    cm = float(m.group(1).replace(",", ".")) if m else None
    return origin, cm


def looks_intimate(message: str) -> bool:
    """True si el texto es de esta función: una palabra clara del tema, «hueso púbico», o un origen + número y nada más."""
    if _INTIMATE_WORD.search(message or ""):
        return True
    origin, cm = parse_message(message)
    return origin == "hueso_pubico" or (origin is not None and cm is not None)


def build_payload(origin: str, cm) -> Dict[str, object]:
    """Valida y arma el registro a guardar."""
    if origin not in ORIGINS:
        raise InvalidMeasure("Indica de dónde mides: hueso púbico, base o perímetro.")
    if isinstance(cm, bool) or not isinstance(cm, (int, float)) or cm != cm or cm in (float("inf"), float("-inf")):
        raise InvalidMeasure("La medida debe ser un número en centímetros.")
    lo, hi = ORIGINS[origin]["range"]
    if cm < lo or cm > hi:
        raise InvalidMeasure(f"Esa medida no es creíble ({lo:g} a {hi:g} cm): revisa cómo mediste.")
    return {"origen": origin, "tipo": ORIGINS[origin]["tipo"], "cm": round(float(cm), 1)}
