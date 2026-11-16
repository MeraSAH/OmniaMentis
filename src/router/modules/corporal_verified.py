"""
* UBICACION: OmniaMentis/src/router/modules/corporal_verified.py
* PROPOSITO: Modulo de composicion corporal con requires_elevated_auth=True. Solo llega aqui una cuenta ADULTA
*            VERIFICADA: el router consulta el verificador (core/verification) antes de invocar handle().
* ESTADO: Produccion
* CAMBIOS 2026-11-15: la verificacion de adultos ya existe (cedula + rostro, revision manual en el panel local
*            del Fons). El calculo de % de grasa y somatotipo vive en NutriVida (core/health/body.py); este
*            modulo orienta y NO duplica formulas.
"""

import logging
from typing import List

from core.health import intimate
from core.health.nutrition import InvalidMeasure
from .base_module import OmniaModule, OmniaContext, ModuleResponse


class CorporalVerifiedModule(OmniaModule):

    @property
    def name(self) -> str:
        return "Corporal Verified"

    @property
    def requires_elevated_auth(self) -> bool:
        return True

    def keywords(self) -> List[str]:
        return [
            "medidas", "porcentaje de grasa", "composicion corporal",
            "composición corporal", "cintura", "circunferencia",
            "imc", "indice de masa", "índice de masa", "progreso fisico",
            "progreso físico", "foto de progreso", "antes y despues",
            "antes y después", "medida intima", "medida íntima", "miembro viril",
            "longitud peneana", "hueso pubico", "hueso púbico",
        ]

    def handle(self, message: str, context: OmniaContext) -> ModuleResponse:
        if intimate.looks_intimate(message):
            return self._intimate(message, context)
        return ModuleResponse(
            text=(
                "📏 Corporal verificado: ya puedes usarlo.\n\n"
                "Para calcular tu % de grasa y tu somatotipo dime: si eres hombre o mujer, tu peso, tu altura y "
                "las medidas de cuello, cintura, brazo y pantorrilla (y la cadera si eres mujer). "
                "Por ejemplo: «soy hombre, peso 70 kg, mido 175 cm, cuello 38, cintura 85, brazo 32, "
                "pantorrilla 36».\n\n"
                "Las fotos de progreso llegarán más adelante. La medida íntima es opcional y se activa solo "
                "con tu consentimiento en el panel de Corporal."
            ),
            module_name=self.name,
            data={"status": "verified", "domain": "body_composition"},
        )

    # ------------------------------------------------------------------ medida íntima (opcional)
    def _intimate(self, message: str, context: OmniaContext) -> ModuleResponse:
        """Registra la medida solo si hay consentimiento vigente. El módulo no decide nada: pregunta al verificador."""
        v = context.verification
        try:
            allowed = bool(v is not None and v.can_use_intimate_measure(context.user_id))
        except Exception:
            allowed = False
        if not allowed:
            return ModuleResponse(
                text=("Esa medida es opcional y necesita tu consentimiento expreso. Actívalo en Corporal, sección "
                      "«Medida sensible». No guardé nada."),
                module_name=self.name, data={"status": "consent_required"})
        origin, cm = intimate.parse_message(message)
        if origin is None or cm is None:
            return ModuleResponse(
                text=("Dime de dónde mides y cuántos cm: «hueso púbico 15.2», «base 14.5» o «perímetro 12». "
                      "No guardé nada."),
                module_name=self.name, data={"status": "need_more"})
        try:
            payload = intimate.build_payload(origin, cm)
        except InvalidMeasure as e:
            return ModuleResponse(text=f"{e} No guardé nada.", module_name=self.name,
                                  data={"status": "invalid"})
        saved = False
        if context.data_store is not None:
            try:
                context.data_store.add(context.user_id, self.name, "medida_intima", dict(payload))
                saved = True
            except Exception as e:
                logging.getLogger(__name__).warning("Corporal: no se pudo guardar la medida: %s", type(e).__name__)
        label = intimate.ORIGINS[origin]["label"]
        text = f"✅ Registrado: {label} = {payload['cm']} cm." if saved else (
            f"{label}: {payload['cm']} cm. No pude guardarlo ahora mismo.")
        return ModuleResponse(
            text=text + " Es solo un dato tuyo: no se compara ni se califica, y no afecta tu sexualidad.",
            module_name=self.name, data={"status": "saved" if saved else "not_saved", **payload})
