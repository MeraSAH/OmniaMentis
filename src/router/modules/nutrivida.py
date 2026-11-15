"""
* UBICACIÓN: OmniaMentis/src/router/modules/nutrivida.py
* PROPÓSITO: Módulo enrutable de nutrición. NO calcula nada por su cuenta:
*            usa el motor (core/health/nutrition.py) y guarda en el almacén
*            único que le entrega el contexto. Solo presenta el resultado.
* DEPENDENCIAS: base_module.py, core/health/nutrition.py
* CREADO: 2026-06-18
* ÚLTIMA MODIFICACIÓN: 2026-11-15
* ESTADO: Producción
*
* CAMBIO 2026-10-18: deja de ser un stub. Calcula IMC y vasos de agua (y calorías
* diarias solo a adultos) a partir del mensaje. Para 13-17 años no clasifica el
* IMC, no calcula calorías y nunca habla de metas de bajar de peso.
* Aún NO hay base de alimentos: no se inventan calorías de comidas.
*
* CAMBIO 2026-11-15: composición corporal (solo adultos): % de grasa por circunferencias (Marina de EE. UU.) y
* somatotipo estimado con cinta métrica y báscula (core/health/body.py). Se guarda como «composicion».
"""

import logging
from typing import List

from core.health import body
from core.health import nutrition as nut
from .base_module import OmniaModule, OmniaContext, ModuleResponse

logger = logging.getLogger(__name__)

MODULE_NAME = "NutriVida"
NOT_MEDICAL = "Es una estimación general, no un diagnóstico ni una pauta médica."


class NutriVidaModule(OmniaModule):

    @property
    def name(self) -> str:
        return MODULE_NAME

    def keywords(self) -> List[str]:
        return [
            "comida", "comer", "dieta", "nutricion", "nutrición",
            "calorias", "calorías", "macros", "proteina", "proteína",
            "carbohidratos", "grasas", "receta", "alimentacion",
            "alimentación", "peso corporal", "bajar de peso", "subir masa",
            "imc", "indice de masa corporal", "índice de masa corporal",
            "vasos de agua", "hidratacion", "hidratación",
            "y mido", "mido 1", "mido 2", "cuanto mido", "cuánto mido",
            "mi peso", "mi altura", "mi estatura",
            # Sin "porcentaje de grasa", "composicion corporal" ni "cintura": son del modulo Corporal
            # Verified (verificacion de edad). NutriVida solo gana con medidas concretas o "somatotipo".
            "somatotipo", "pantorrilla", "cuello",
        ]

    def _resp(self, text: str, status: str, followup: bool = False, data=None) -> ModuleResponse:
        payload = {"status": status, "domain": "nutrition"}
        if data:
            payload.update(data)
        return ModuleResponse(text=text, module_name=self.name,
                              requires_followup=followup, data=payload)

    def handle(self, message: str, context: OmniaContext) -> ModuleResponse:
        is_adult = context.age_band == nut.ADULT
        found = nut.extract_measures(message)

        if body.wants_body_composition(message):
            return self._body(message, found, context)

        # Menores: jamás metas de bajar de peso.
        if not is_adult and nut.wants_weight_loss(message):
            return self._resp(
                "No te voy a proponer metas de bajar de peso ni dietas: a tu edad el cuerpo "
                "está creciendo y eso debe verlo un pediatra o un nutricionista. "
                "Sí puedo ayudarte con hidratación y con calcular tu IMC como dato. "
                "Si algo de tu cuerpo o de tu forma de comer te preocupa, cuéntaselo a un adulto "
                "de confianza o a un profesional de la salud.",
                "minor_safe_redirect")

        if "weight_kg" not in found or "height_cm" not in found:
            return self._resp(
                "Puedo calcular tu IMC y los vasos de agua que te convienen"
                + (", y tus calorías diarias estimadas" if is_adult else "")
                + ". Dime tu peso y tu altura, por ejemplo: «peso 70 kg y mido 175 cm»"
                + (" (para las calorías añade tu edad, si eres hombre o mujer y qué tan activo eres)." if is_adult else ".")
                + " Todavía no tengo una base de alimentos, así que no puedo darte las calorías de una comida concreta.",
                "needs_measures", followup=True)

        try:
            bmi = nut.compute_bmi(found["weight_kg"], found["height_cm"])
            glasses = nut.water_glasses(found["weight_kg"], context.age_band)
        except nut.InvalidMeasure as exc:
            return self._resp(f"No pude calcularlo: {exc} Revisa tus datos e inténtalo de nuevo.",
                              "invalid_measures", followup=True)

        category = nut.bmi_category(bmi, context.age_band)
        lines = [f"Tu IMC es {bmi}."]
        if category:
            lines.append(f"En personas adultas eso corresponde a: {category}.")
            if category in ("bajo peso", "obesidad"):
                lines.append("Conviene hablarlo con un profesional de la salud.")
        else:
            lines.append("A tu edad el IMC se interpreta con percentiles según edad y sexo, "
                         "así que no lo clasifico: consulta a tu pediatra o nutricionista.")
        lines.append(f"Hidratación orientativa: {glasses} vasos de 250 ml al día.")

        result = {"bmi": bmi, "bmi_category": category, "water_glasses": glasses,
                  "weight_kg": found["weight_kg"], "height_cm": found["height_cm"]}
        status = "calculated"
        followup = False

        if is_adult:
            missing = [k for k in ("age", "sex", "activity") if k not in found]
            if not missing:
                try:
                    kcal = nut.daily_calories(found["weight_kg"], found["height_cm"], found["age"],
                                              found["sex"], found["activity"], context.age_band)
                    result["daily_calories"] = kcal
                    lines.append(f"Calorías diarias estimadas para mantener tu peso: {kcal} kcal.")
                except nut.InvalidMeasure as exc:
                    lines.append(f"No pude estimar las calorías: {exc}")
            else:
                names = {"age": "tu edad", "sex": "si eres hombre o mujer", "activity": "tu nivel de actividad (sedentario, ligero, moderado o muy activo)"}
                lines.append("Para estimar tus calorías diarias dime además " + ", ".join(names[k] for k in missing) + ".")
                followup = True
        lines.append(NOT_MEDICAL)

        saved = False
        if context.data_store is not None:
            try:
                context.data_store.add(context.user_id, self.name, "calculo", dict(result))
                saved = True
            except Exception as exc:  # el cálculo sigue valiendo aunque no se guarde
                logger.warning("NutriVida: no se pudo guardar el cálculo: %s", exc)
        result["saved"] = saved
        return self._resp("\n".join(lines), status, followup=followup, data=result)

    # ------------------------------------------------------------------ composición corporal
    _NEEDS = {"sex": "si eres hombre o mujer", "weight_kg": "tu peso en kg", "height_cm": "tu altura en cm",
              "neck_cm": "el cuello en cm (justo debajo de la nuez)",
              "waist_cm": "la cintura en cm (en el ombligo si eres hombre; en el punto más estrecho si eres mujer)",
              "hip_cm": "la cadera en cm (punto más ancho de los glúteos)"}

    def _body(self, message: str, found: dict, context: OmniaContext) -> ModuleResponse:
        if context.age_band != nut.ADULT:
            return self._resp(
                "El porcentaje de grasa y el somatotipo se calculan con fórmulas hechas para personas adultas, "
                "así que a tu edad no los calculo. Sí puedo darte tu IMC como dato y tu hidratación. "
                "Si algo de tu cuerpo te preocupa, cuéntaselo a un adulto de confianza o a tu pediatra.",
                "minor_not_applicable")
        data = dict(found)
        data.update(body.extract_girths(message))
        need = ["sex", "weight_kg", "height_cm", "neck_cm", "waist_cm"] + (["hip_cm"] if data.get("sex") == "mujer" else [])
        missing = [k for k in need if k not in data]
        if missing:
            return self._resp(
                "Para estimar tu composición corporal dime " + ", ".join(self._NEEDS[k] for k in missing) + ". "
                "Ejemplo: «soy hombre, peso 70 kg, mido 175 cm, cuello 38, cintura 85, brazo 32, pantorrilla 36». "
                "Con brazo y pantorrilla (flexionado al máximo y en su punto más ancho) también estimo tu somatotipo.",
                "needs_measures", followup=True)
        sex = data["sex"]
        full = "arm_cm" in data and "calf_cm" in data
        try:
            if full:
                res = body.estimate_somatotype(sex, data["weight_kg"], data["height_cm"], data["neck_cm"],
                                               data["waist_cm"], data.get("hip_cm"), data["arm_cm"], data["calf_cm"])
            else:
                fat = body.navy_body_fat(sex, data["height_cm"], data["neck_cm"], data["waist_cm"], data.get("hip_cm"))
                res = {"body_fat": fat, "fat_category": body.fat_category(sex, fat)}
            bmi = nut.compute_bmi(data["weight_kg"], data["height_cm"])
        except nut.InvalidMeasure as exc:
            return self._resp(f"No pude calcularlo: {exc} Revisa tus medidas e inténtalo de nuevo.",
                              "invalid_measures", followup=True)

        lines = [f"Porcentaje de grasa estimado: {res['body_fat']} % (referencia general: {res['fat_category']}).",
                 f"Tu IMC es {bmi}.",
                 "El método de circunferencias tiene un margen de error de varios puntos: sirve para ver tu "
                 "tendencia midiéndote siempre igual, no como medición exacta."]
        if full:
            lines.insert(1, f"Somatotipo estimado: endomorfia {res['endo']}, mesomorfia {res['meso']}, "
                            f"ectomorfia {res['ecto']} → {res['somatotype']}.")
            lines.append("La ectomorfia usa la fórmula de Heath-Carter; la endomorfia y la mesomorfia son "
                         "estimaciones de OmniaMentis con cinta y báscula, no una medición con plicómetro.")
        else:
            lines.append("Si añades brazo y pantorrilla (en cm) también estimo tu somatotipo.")
        lines.append(NOT_MEDICAL)

        payload = {"sex": sex, "weight_kg": data["weight_kg"], "height_cm": data["height_cm"], "bmi": bmi,
                   "neck_cm": data["neck_cm"], "waist_cm": data["waist_cm"], **res}
        for k in ("hip_cm", "arm_cm", "calf_cm"):
            if k in data:
                payload[k] = data[k]
        saved = False
        if context.data_store is not None:
            try:
                context.data_store.add(context.user_id, self.name, "composicion", dict(payload))
                saved = True
            except Exception as exc:
                logger.warning("NutriVida: no se pudo guardar la composición: %s", exc)
        payload["saved"] = saved
        return self._resp("\n".join(lines), "body_composition", followup=not full, data=payload)
