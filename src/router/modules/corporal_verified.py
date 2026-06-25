"""
* UBICACIÓN: OmniaMentis/src/router/modules/corporal_verified.py
* PROPÓSITO: Módulo enrutable para temas de composición corporal, medidas
*            y seguimiento físico verificado.
* DEPENDENCIAS: src/router/modules/base_module.py
* CREADO: 2026-06-18
* ÚLTIMA MODIFICACIÓN: 2026-06-18
* ESTADO: Producción (lógica de routing) / Stub funcional (lógica de
*         dominio — proyecto independiente aún no integrado)
"""

from typing import List

from .base_module import OmniaModule, OmniaContext, ModuleResponse


class CorporalVerifiedModule(OmniaModule):
    """
    Captura mensajes relacionados con composición corporal, medidas
    antropométricas y seguimiento físico verificado (fotos, % de grasa,
    circunferencias).

    ESTADO ACTUAL: routing real; el dominio de verificación y tracking
    corporal pertenece al proyecto Corporal Verified, independiente y
    aún no integrado.
    """

    @property
    def name(self) -> str:
        return "Corporal Verified"

    def keywords(self) -> List[str]:
        return [
            "medidas", "porcentaje de grasa", "composicion corporal",
            "composición corporal", "cintura", "circunferencia",
            "imc", "indice de masa", "índice de masa", "progreso fisico",
            "progreso físico", "foto de progreso", "antes y despues",
            "antes y después",
        ]

    def handle(self, message: str, context: OmniaContext) -> ModuleResponse:
        text = (
            f"📏 Detecté que tu consulta es sobre composición corporal "
            f"o medidas.\n\n"
            f"El módulo Corporal Verified (registro de medidas, "
            f"verificación de progreso, % de grasa corporal) es un "
            f"proyecto independiente aún no conectado a esta API.\n\n"
            f"♋ Cuando esté integrado, esta consulta activará el "
            f"registro y análisis real de tus medidas."
        )
        return ModuleResponse(
            text=text,
            module_name=self.name,
            requires_followup=False,
            data={"status": "not_integrated", "domain": "body_composition"},
        )