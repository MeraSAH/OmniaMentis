"""
* UBICACIÓN: OmniaMentis/src/core/health/body.py
* PROPÓSITO: Composición corporal para NutriVida dentro del motor de OmniaMentis: % de grasa (método de
*            circunferencias de la Marina de EE. UU.), somatotipo (Heath-Carter completo y una versión
*            «solo cinta métrica y báscula») y extracción de las medidas desde un mensaje.
*            Funciones puras (sin E/S): el módulo NutriVida solo presenta.
* DEPENDENCIAS: math, re (stdlib); core/health/nutrition.py (rangos de peso y altura)
* CREADO: 2026-11-15
* ESTADO: Producción
*
* ORIGEN DE LAS FÓRMULAS (decididas por el dueño del proyecto):
*   - % de grasa: Hodgdon y Beckett (Marina de EE. UU.), medidas en cm, log10.
*   - Somatotipo completo: Heath-Carter (plicómetro y antropómetro). Disponible como función; el chat pide
*     solo las medidas de cinta, así que usa la versión estimada.
*   - Versión estimada (cinta y báscula): la ectomorfia es EXACTAMENTE la de Heath-Carter (índice ponderal);
*     la endomorfia y la mesomorfia son ESTIMACIONES PROPIAS de OmniaMentis, no Heath-Carter oficial
*     (ver estimate_endomorphy y estimate_mesomorphy). Se presentan siempre como estimación.
*
* SEGURIDAD: las fórmulas son para PERSONAS ADULTAS. Quien llame a este motor debe comprobar la edad; el módulo
*   NutriVida lo hace y a menores no les calcula nada de esto.
"""

import math
import re
from typing import Dict, Optional, Tuple

from core.health.nutrition import InvalidMeasure, MAX_HEIGHT_CM, MAX_WEIGHT_KG, MIN_HEIGHT_CM, MIN_WEIGHT_KG, _num

NECK = (20.0, 70.0)
WAIST = (40.0, 200.0)
HIP = (50.0, 200.0)
ARM = (15.0, 70.0)
CALF = (15.0, 70.0)
SKINFOLD_MM = (2.0, 80.0)
HUMERUS_CM = (4.0, 12.0)
FEMUR_CM = (6.0, 15.0)
FAT_RANGE = (2.0, 60.0)       # un resultado fuera de esto casi seguro viene de una medida mal tomada
SEXES = ("hombre", "mujer")


def _sex(sex) -> str:
    if sex not in SEXES:
        raise InvalidMeasure("Indica si eres hombre o mujer.")
    return sex


# --------------------------------------------------------------------------- % de grasa
def navy_body_fat(sex, height_cm, neck_cm, waist_cm, hip_cm=None) -> float:
    """% de grasa corporal, método de circunferencias de la Marina de EE. UU. (1 decimal).
    Hombre: cintura a nivel del ombligo. Mujer: cintura en su punto más estrecho y cadera en el más ancho."""
    s = _sex(sex)
    h = _num(height_cm, "La altura", MIN_HEIGHT_CM, MAX_HEIGHT_CM)
    neck = _num(neck_cm, "El cuello", *NECK)
    waist = _num(waist_cm, "La cintura", *WAIST)
    if s == "hombre":
        diff = waist - neck
        if diff <= 0:
            raise InvalidMeasure("La cintura debe ser mayor que el cuello: revisa las dos medidas.")
        pct = 495 / (1.0324 - 0.19077 * math.log10(diff) + 0.15456 * math.log10(h)) - 450
    else:
        if hip_cm is None:
            raise InvalidMeasure("Para mujeres hace falta también la cadera.")
        hip = _num(hip_cm, "La cadera", *HIP)
        total = waist + hip - neck
        if total <= 0:
            raise InvalidMeasure("La suma cintura + cadera debe ser mayor que el cuello: revisa las medidas.")
        pct = 495 / (1.29579 - 0.35004 * math.log10(total) + 0.22100 * math.log10(h)) - 450
    if not math.isfinite(pct) or pct < FAT_RANGE[0] or pct > FAT_RANGE[1]:
        raise InvalidMeasure("Con esas medidas el resultado no es creíble: revisa cómo te mediste "
                             "(cuello bajo la nuez, cintura en el ombligo).")
    return round(pct, 1)


# Rangos de referencia generales (ACE): (límite superior inclusivo, nombre). Sin diagnóstico.
_FAT_BANDS = {
    "hombre": [(5.9, "grasa esencial"), (13.9, "atlético"), (17.9, "en forma"), (24.9, "aceptable"), (1e9, "obesidad")],
    "mujer": [(13.9, "grasa esencial"), (20.9, "atlético"), (24.9, "en forma"), (31.9, "aceptable"), (1e9, "obesidad")],
}


def fat_category(sex, pct: float) -> str:
    for limit, name in _FAT_BANDS[_sex(sex)]:
        if pct <= limit:
            return name
    return "obesidad"


# --------------------------------------------------------------------------- somatotipo
def ponderal_index(height_cm, weight_kg) -> float:
    h = _num(height_cm, "La altura", MIN_HEIGHT_CM, MAX_HEIGHT_CM)
    w = _num(weight_kg, "El peso", MIN_WEIGHT_KG, MAX_WEIGHT_KG)
    return h / (w ** (1.0 / 3.0))


def ectomorphy(height_cm, weight_kg) -> float:
    """Ectomorfia de Heath-Carter (linealidad) a partir del índice ponderal."""
    pi = ponderal_index(height_cm, weight_kg)
    if pi >= 40.75:
        return round(0.732 * pi - 28.58, 1)
    if pi > 38.25:
        return round(0.463 * pi - 17.63, 1)
    return 0.1


def heath_carter(height_cm, weight_kg, triceps_mm, subscapular_mm, supraspinal_mm, calf_skinfold_mm,
                 arm_flexed_cm, calf_cm, humerus_cm, femur_cm) -> Tuple[float, float, float]:
    """Somatotipo antropométrico completo (endomorfia, mesomorfia, ectomorfia). Requiere plicómetro y
    antropómetro (medidas tomadas por alguien con el instrumental)."""
    h = _num(height_cm, "La altura", MIN_HEIGHT_CM, MAX_HEIGHT_CM)
    tri = _num(triceps_mm, "El pliegue del tríceps", *SKINFOLD_MM)
    sub = _num(subscapular_mm, "El pliegue subescapular", *SKINFOLD_MM)
    sup = _num(supraspinal_mm, "El pliegue supraespinal", *SKINFOLD_MM)
    cal = _num(calf_skinfold_mm, "El pliegue de la pantorrilla", *SKINFOLD_MM)
    arm = _num(arm_flexed_cm, "El perímetro del brazo", *ARM)
    calf = _num(calf_cm, "El perímetro de la pantorrilla", *CALF)
    hum = _num(humerus_cm, "El diámetro del húmero", *HUMERUS_CM)
    fem = _num(femur_cm, "El diámetro del fémur", *FEMUR_CM)
    x = (tri + sub + sup) * (170.18 / h)
    endo = -0.7182 + 0.1451 * x - 0.00068 * x ** 2 + 0.0000014 * x ** 3
    arm_corr = arm - tri / 10.0
    calf_corr = calf - cal / 10.0
    meso = 0.858 * hum + 0.601 * fem + 0.188 * arm_corr + 0.161 * calf_corr - 0.131 * h + 4.5
    return round(endo, 1), round(meso, 1), ectomorphy(h, weight_kg)


def estimate_endomorphy(body_fat_pct: float) -> float:
    """ESTIMACIÓN propia: % de grasa de la Marina dividido entre 4.5 (mínimo 1.0, máximo 12.0)."""
    return round(max(1.0, min(12.0, body_fat_pct / 4.5)), 1)


def estimate_mesomorphy(weight_kg, height_cm, body_fat_pct: float, arm_cm, calf_cm) -> float:
    """ESTIMACIÓN propia (no es Heath-Carter oficial) con solo cinta y báscula:
    índice de masa libre de grasa (FFMI = masa magra / altura²) mapeado a una escala 0.5–9 como
    0.6·FFMI − 7.4, más un ajuste de ±1 según los perímetros de brazo y pantorrilla relativos a la altura
    (0.20 de la altura = promedio)."""
    w = _num(weight_kg, "El peso", MIN_WEIGHT_KG, MAX_WEIGHT_KG)
    h = _num(height_cm, "La altura", MIN_HEIGHT_CM, MAX_HEIGHT_CM)
    arm = _num(arm_cm, "El perímetro del brazo", *ARM)
    calf = _num(calf_cm, "El perímetro de la pantorrilla", *CALF)
    lean = w * (1 - body_fat_pct / 100.0)
    ffmi = lean / ((h / 100.0) ** 2)
    ratio = ((arm + calf) / 2.0) / h
    adjust = max(-1.0, min(1.0, (ratio - 0.20) * 10.0))
    return round(max(0.5, min(9.0, 0.6 * ffmi - 7.4 + adjust)), 1)


def estimate_somatotype(sex, weight_kg, height_cm, neck_cm, waist_cm, hip_cm, arm_cm, calf_cm) -> Dict[str, float]:
    """Versión «solo cinta métrica y báscula»: devuelve grasa, categoría, y el somatotipo estimado."""
    fat = navy_body_fat(sex, height_cm, neck_cm, waist_cm, hip_cm)
    endo = estimate_endomorphy(fat)
    meso = estimate_mesomorphy(weight_kg, height_cm, fat, arm_cm, calf_cm)
    ecto = ectomorphy(height_cm, weight_kg)
    return {"body_fat": fat, "fat_category": fat_category(sex, fat), "endo": endo, "meso": meso, "ecto": ecto,
            "somatotype": classify(endo, meso, ecto), **somatochart(endo, meso, ecto)}


def somatochart(endo: float, meso: float, ecto: float) -> Dict[str, float]:
    """Coordenadas de la somatocarta: X = ecto − endo ; Y = 2·meso − (endo + ecto)."""
    return {"chart_x": round(ecto - endo, 1), "chart_y": round(2 * meso - (endo + ecto), 1)}


def classify(endo: float, meso: float, ecto: float) -> str:
    """Nombre simplificado del somatotipo. Un componente domina si supera al siguiente en más de 0.5;
    si dos van parejos se nombran juntos; si los tres van parejos es «central»."""
    comps = sorted([("endomorfo", endo), ("mesomorfo", meso), ("ectomorfo", ecto)], key=lambda c: -c[1])
    (n1, v1), (n2, v2), (n3, v3) = comps
    if v1 - v3 <= 0.5:
        return "central (equilibrado)"
    if v1 - v2 > 0.5:
        return n1
    return f"{n1}-{n2} (mixto)"


# --------------------------------------------------------------------------- texto libre
_NUM = r"(\d{1,3}(?:[.,]\d{1,2})?)"
_PARTS = {
    "neck_cm": re.compile(r"\bcuello\b[^\d\n]{0,12}" + _NUM, re.I),
    "waist_cm": re.compile(r"\bcintura\b[^\d\n]{0,12}" + _NUM, re.I),
    "hip_cm": re.compile(r"\bcadera\b[^\d\n]{0,12}" + _NUM, re.I),
    "arm_cm": re.compile(r"\b(?:brazo|biceps|bíceps)\b[^\d\n]{0,12}" + _NUM, re.I),
    "calf_cm": re.compile(r"\bpantorrilla\b[^\d\n]{0,12}" + _NUM, re.I),
}
_WANTS = re.compile(r"somatotipo|somatotype|porcentaje de grasa|% de grasa|grasa corporal|composici[oó]n corporal|"
                    r"\bcintura\b|\bcuello\b\s*(?:de|=|:)?\s*\d", re.I)


def extract_girths(message: str) -> Dict[str, float]:
    """Cuello, cintura, cadera, brazo y pantorrilla (cm) de un texto libre. Solo lo que encuentra; no valida."""
    text = message or ""
    out: Dict[str, float] = {}
    for key, rx in _PARTS.items():
        m = rx.search(text)
        if m:
            out[key] = float(m.group(1).replace(",", "."))
    return out


def wants_body_composition(message: str) -> bool:
    return bool(_WANTS.search(message or ""))
