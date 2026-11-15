"""
* UBICACION: OmniaMentis/src/router/modules/corporal_verified.py
* PROPOSITO: Modulo de composicion corporal con requires_elevated_auth=True. Solo llega aqui una cuenta ADULTA
*            VERIFICADA: el router consulta el verificador (core/verification) antes de invocar handle().
* ESTADO: Produccion
* CAMBIOS 2026-11-15: la verificacion de adultos ya existe (cedula + rostro, revision manual en el panel local
*            del Fons). El calculo de % de grasa y somatotipo vive en NutriVida (core/health/body.py); este
*            modulo orienta y NO duplica formulas.
"""

from typing import List
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
            "antes y después",
        ]

    def handle(self, message: str, context: OmniaContext) -> ModuleResponse:
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
