"""
* UBICACIÓN: OmniaMentis/src/router/modules/nutrivida.py
* PROPÓSITO: Módulo enrutable para temas de nutrición, dieta y alimentación.
* DEPENDENCIAS: src/router/modules/base_module.py
* CREADO: 2026-06-18
* ÚLTIMA MODIFICACIÓN: 2026-06-18
* ESTADO: Producción (lógica de routing) / Stub funcional (lógica de
*         dominio nutricional — el motor real de NutriVida es un
*         proyecto independiente aún no integrado)
"""

from typing import List

from .base_module import OmniaModule, OmniaContext, ModuleResponse


class NutriVidaModule(OmniaModule):
    """
    Captura mensajes relacionados con nutrición, dietas, calorías y
    hábitos alimenticios, y los enruta hacia el dominio NutriVida.

    ESTADO ACTUAL: este módulo reconoce y captura correctamente la
    intención del usuario (routing real, no simulado), pero el cálculo
    de macros/calorías y la generación de planes nutricionales
    pertenecen al proyecto NutriVida, que es independiente y aún no
    está integrado vía API. Por ahora, `handle()` devuelve una
    respuesta honesta indicando el estado, en vez de inventar números.
    """

    @property
    def name(self) -> str:
        return "NutriVida"

    def keywords(self) -> List[str]:
        return [
            "comida", "comer", "dieta", "nutricion", "nutrición",
            "calorias", "calorías", "macros", "proteina", "proteína",
            "carbohidratos", "grasas", "receta", "alimentacion",
            "alimentación", "peso corporal", "bajar de peso", "subir masa",
        ]

    def handle(self, message: str, context: OmniaContext) -> ModuleResponse:
        text = (
            f"🥗 Detecté que tu consulta es sobre nutrición.\n\n"
            f"El módulo NutriVida (cálculo de macros, planes de comida, "
            f"seguimiento calórico) es un proyecto independiente que "
            f"todavía no está conectado a esta API. Por ahora puedo "
            f"acompañarte de forma conversacional, pero no puedo darte "
            f"cifras nutricionales precisas todavía.\n\n"
            f"♋ Cuando NutriVida esté integrado, esta misma pregunta "
            f"activará el motor real de cálculo."
        )
        return ModuleResponse(
            text=text,
            module_name=self.name,
            requires_followup=False,
            data={"status": "not_integrated", "domain": "nutrition"},
        )