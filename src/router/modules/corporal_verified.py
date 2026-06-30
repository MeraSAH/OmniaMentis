"""
* UBICACION: OmniaMentis/src/router/modules/corporal_verified.py
* PROPOSITO: Modulo de composicion corporal con requires_elevated_auth=True
* ESTADO: Produccion
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
                "📏 Detecté que tu consulta es sobre composición corporal.\n\n"
                "Corporal Verified (medidas, % de grasa, verificación de progreso) "
                "es un proyecto independiente aún no integrado.\n\n"
                "♋ Cuando esté activo, registraré y analizaré tus medidas."
            ),
            module_name=self.name,
            data={"status": "not_integrated", "domain": "body_composition"},
        )