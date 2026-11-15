"""
* UBICACION: OmniaMentis/src/core/health/nutrition.py
* PROPOSITO: Calculos de NutriVida dentro del motor de OmniaMentis: IMC, agua y
*            calorias diarias, mas la extraccion de medidas desde un mensaje.
*            Funciones puras (sin E/S): el modulo NutriVida solo presenta.
* DEPENDENCIAS: re, math (stdlib)
* CREADO: 2026-10-18
* ESTADO: Produccion
*
* DECISIONES DE SEGURIDAD (menores 13-17):
*   - El IMC de adolescentes se interpreta con percentiles por edad y sexo
*     (tablas OMS). No se incluyen aqui, asi que para menores se calcula el
*     numero pero NO se clasifica (nada de "sobrepeso"/"bajo peso").
*   - Harris-Benedict es para adultos: a menores NO se les calculan calorias.
*   - Nunca metas de deficit calorico ni de bajar de peso para menores.
*   - Rangos de validacion estrictos: un dato absurdo no se calcula ni se guarda.
* SOMATOTIPO: no se implementa todavia. La formula usada por el sitio de
*   NutriVida no esta en el repositorio y no se inventa una.
"""

import math
import re
from typing import Dict, Optional

MIN_WEIGHT_KG, MAX_WEIGHT_KG = 20.0, 300.0
MIN_HEIGHT_CM, MAX_HEIGHT_CM = 100.0, 250.0
MIN_AGE, MAX_AGE = 13, 110
GLASS_ML = 250
ACTIVITY_FACTORS = {"sedentario": 1.2, "ligero": 1.375, "moderado": 1.55, "muy_activo": 1.725}
ADULT = "adult"


class InvalidMeasure(ValueError):
    """Medida fuera de rango o no numerica."""


class NotApplicable(ValueError):
    """El calculo no aplica para este rango de edad."""


def _num(value, name: str, lo: float, hi: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise InvalidMeasure(f"{name} debe ser un numero.")
    v = float(value)
    if not math.isfinite(v) or v < lo or v > hi:
        raise InvalidMeasure(f"{name} fuera de rango ({lo:g}-{hi:g}).")
    return v


def compute_bmi(weight_kg, height_cm) -> float:
    """IMC = kg / m^2, redondeado a 1 decimal."""
    w = _num(weight_kg, "El peso", MIN_WEIGHT_KG, MAX_WEIGHT_KG)
    h = _num(height_cm, "La altura", MIN_HEIGHT_CM, MAX_HEIGHT_CM)
    return round(w / ((h / 100.0) ** 2), 1)


def bmi_category(bmi: float, age_band: str) -> Optional[str]:
    """Categoria OMS para adultos. Para menores devuelve None (requiere percentil)."""
    if age_band != ADULT:
        return None
    if bmi < 18.5:
        return "bajo peso"
    if bmi < 25:
        return "saludable"
    if bmi < 30:
        return "sobrepeso"
    return "obesidad"


def water_glasses(weight_kg, age_band: str) -> int:
    """Vasos de 250 ml al dia. Adultos: ~35 ml/kg (limite 6-16). Menores: 8 fijos."""
    if age_band != ADULT:
        return 8
    w = _num(weight_kg, "El peso", MIN_WEIGHT_KG, MAX_WEIGHT_KG)
    return max(6, min(16, math.ceil(w * 35 / GLASS_ML)))


def daily_calories(weight_kg, height_cm, age, sex: str, activity: str, age_band: str) -> int:
    """Gasto diario estimado (Harris-Benedict revisada, Roza-Shizgal 1984) x actividad.
    Solo adultos. Estimacion general, no pauta medica."""
    if age_band != ADULT:
        raise NotApplicable("Las calorias diarias solo se calculan para personas adultas.")
    w = _num(weight_kg, "El peso", MIN_WEIGHT_KG, MAX_WEIGHT_KG)
    h = _num(height_cm, "La altura", MIN_HEIGHT_CM, MAX_HEIGHT_CM)
    a = _num(age, "La edad", 18, MAX_AGE)
    if sex not in ("hombre", "mujer"):
        raise InvalidMeasure("Indica si eres hombre o mujer.")
    factor = ACTIVITY_FACTORS.get(activity)
    if factor is None:
        raise InvalidMeasure("Nivel de actividad desconocido.")
    if sex == "hombre":
        bmr = 88.362 + 13.397 * w + 4.799 * h - 5.677 * a
    else:
        bmr = 447.593 + 9.247 * w + 3.098 * h - 4.330 * a
    return int(round(bmr * factor))


# ---------------------------------------------------------------- extraccion de texto
_NUM = r"(\d{1,3}(?:[.,]\d{1,2})?)"
_W_UNIT = re.compile(_NUM + r"\s*(?:kg|kgs|kilos?|kilogramos?)\b", re.I)
_W_WORD = re.compile(r"\bpeso\b[^\d]{0,15}" + _NUM, re.I)
_H_CM = re.compile(r"\b(\d{3}(?:[.,]\d)?)\s*cm\b", re.I)
_H_M = re.compile(r"\b([12][.,]\d{1,2})\s*(?:m|mts?|metros?)?\b(?!\s*(?:kg|cm|años))", re.I)
_H_WORD = re.compile(r"\b(?:mido|altura|estatura|talla)\b[^\d]{0,15}(\d{1,3}(?:[.,]\d{1,2})?)", re.I)
_AGE = re.compile(r"\b(\d{2,3})\s*años\b", re.I)
_MALE = re.compile(r"\b(hombre|varon|varón|masculino)\b", re.I)
_FEMALE = re.compile(r"\b(mujer|femenino)\b", re.I)
_LOSS = re.compile(r"bajar de peso|adelgazar|perder peso|déficit|deficit|quemar grasa|bajar kilos", re.I)


def _f(text: str) -> float:
    return float(text.replace(",", "."))


def wants_weight_loss(message: str) -> bool:
    return bool(_LOSS.search(message or ""))


def extract_measures(message: str) -> Dict[str, object]:
    """Saca peso (kg), altura (cm), edad, sexo y actividad de un texto libre.
    Devuelve solo lo que encuentra; nunca lanza. No valida rangos."""
    text = message or ""
    out: Dict[str, object] = {}
    m = _W_UNIT.search(text) or _W_WORD.search(text)
    if m:
        out["weight_kg"] = _f(m.group(1))
    h = None
    m = _H_CM.search(text)
    if m:
        h = _f(m.group(1))
    else:
        m = _H_WORD.search(text)
        if m:
            v = _f(m.group(1))
            h = v * 100 if v < 3 else v
        else:
            m = _H_M.search(text)
            if m:
                h = _f(m.group(1)) * 100
    if h is not None:
        out["height_cm"] = round(h, 1)
    m = _AGE.search(text)
    if m:
        out["age"] = int(m.group(1))
    if _MALE.search(text) and not _FEMALE.search(text):
        out["sex"] = "hombre"
    elif _FEMALE.search(text) and not _MALE.search(text):
        out["sex"] = "mujer"
    low = text.lower()
    if "muy activ" in low:
        out["activity"] = "muy_activo"
    elif "sedentari" in low:
        out["activity"] = "sedentario"
    elif "moderad" in low:
        out["activity"] = "moderado"
    elif "ligeramente activ" in low or "poco activ" in low:
        out["activity"] = "ligero"
    return out
