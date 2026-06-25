"""
* UBICACIÓN: OmniaMentis/src/router/modules/omnia_habits.py
* PROPÓSITO: Módulo enrutable para temas de hábitos diarios, rutinas y
*            seguimiento de constancia.
* DEPENDENCIAS: src/router/modules/base_module.py
* CREADO: 2026-06-18
* ÚLTIMA MODIFICACIÓN: 2026-06-18
* ESTADO: Producción (lógica de routing) / Stub funcional (lógica de
*         dominio — proyecto independiente aún no integrado)
"""

from typing import List

from .base_module import OmniaModule, OmniaContext, ModuleResponse


class OmniaHabitsModule(OmniaModule):
    """
    Captura mensajes relacionados con la formación y seguimiento de
    hábitos diarios (rachas, recordatorios, constancia).

    ESTADO ACTUAL: routing real; el dominio de tracking de hábitos
    pertenece al proyecto OmniaHabits, independiente y aún no
    integrado.
    """

    @property
    def name(self) -> str:
        return "OmniaHabits"

    def keywords(self) -> List[str]:
        return [
            "habito", "hábito", "racha", "constancia", "rutina diaria",
            "recordatorio", "meta diaria", "objetivo diario",
            "seguimiento de habitos", "seguimiento de hábitos",
            "streak", "disciplina",
        ]

    def handle(self, message: str, context: OmniaContext) -> ModuleResponse:
        text = (
            f"📅 Detecté que tu consulta es sobre hábitos o constancia.\n\n"
            f"El módulo OmniaHabits (rachas, recordatorios, seguimiento "
            f"de metas diarias) es un proyecto independiente aún no "
            f"conectado a esta API.\n\n"
            f"♋ Mientras tanto, puedo acompañarte conversacionalmente "
            f"en tu proceso. Cuando OmniaHabits esté integrado, esta "
            f"consulta activará el tracking real."
        )
        return ModuleResponse(
            text=text,
            module_name=self.name,
            requires_followup=False,
            data={"status": "not_integrated", "domain": "habits"},
        )