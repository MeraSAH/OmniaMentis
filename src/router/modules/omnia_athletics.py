"""
* UBICACIÓN: OmniaMentis/src/router/modules/omnia_athletics.py
* PROPÓSITO: Módulo enrutable para temas de entrenamiento físico, ejercicio
*            y rendimiento deportivo.
* DEPENDENCIAS: src/router/modules/base_module.py
* CREADO: 2026-06-18
* ÚLTIMA MODIFICACIÓN: 2026-06-18
* ESTADO: Producción (lógica de routing) / Stub funcional (lógica de
*         dominio deportivo — proyecto independiente aún no integrado)
"""

from typing import List

from .base_module import OmniaModule, OmniaContext, ModuleResponse


class OmniaAthleticsModule(OmniaModule):
    """
    Captura mensajes relacionados con entrenamiento, ejercicio físico,
    rutinas y rendimiento deportivo.

    ESTADO ACTUAL: igual que NutriVida, el routing es real pero la
    generación de rutinas y el tracking de rendimiento pertenecen al
    proyecto OmniaAthletics, independiente y no integrado aún.
    """

    @property
    def name(self) -> str:
        return "OmniaAthletics"

    def keywords(self) -> List[str]:
        return [
            "entrenar", "entrenamiento", "ejercicio", "rutina", "gym",
            "gimnasio", "pesas", "cardio", "correr", "running",
            "rendimiento deportivo", "musculo", "músculo", "fuerza",
            "resistencia", "repeticiones", "series",
        ]

    def handle(self, message: str, context: OmniaContext) -> ModuleResponse:
        text = (
            f"💪 Detecté que tu consulta es sobre entrenamiento físico.\n\n"
            f"El módulo OmniaAthletics (rutinas personalizadas, tracking "
            f"de rendimiento, progresión de cargas) es un proyecto "
            f"independiente aún no conectado a esta API. Puedo "
            f"conversar contigo sobre el tema, pero no generar rutinas "
            f"estructuradas todavía.\n\n"
            f"♋ Cuando OmniaAthletics esté integrado, esta consulta "
            f"activará el motor real de entrenamiento."
        )
        return ModuleResponse(
            text=text,
            module_name=self.name,
            requires_followup=False,
            data={"status": "not_integrated", "domain": "athletics"},
        )