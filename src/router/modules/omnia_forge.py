"""
* UBICACIÓN: OmniaMentis/src/router/modules/omnia_forge.py
* PROPÓSITO: Módulo enrutable para peticiones de ejecución de código,
*            automatización de tareas y sandbox Python/JavaScript.
* DEPENDENCIAS: src/router/modules/base_module.py
* CREADO: 2026-06-19
* ÚLTIMA MODIFICACIÓN: 2026-06-19
* ESTADO: Producción (routing) / Stub funcional (dominio no integrado)
"""

from typing import List
from .base_module import OmniaModule, OmniaContext, ModuleResponse


class OmniaForgeModule(OmniaModule):
    """
    Captura peticiones de ejecución de fragmentos de código Python o
    JavaScript, automatización de tareas y scripting.

    NOTA DE SEGURIDAD: cuando OmniaForge se integre como dominio real,
    debe correr el código en un sandbox aislado (no en el proceso de
    Flask), con límites estrictos de tiempo de ejecución y sin acceso
    al filesystem del servidor. Esto es responsabilidad de OmniaForge
    como proyecto independiente, no de OmniaMentis.
    """

    @property
    def name(self) -> str:
        return "OmniaForge"

    def keywords(self) -> List[str]:
        return [
            "ejecutar codigo", "ejecutar código", "correr script",
            "automatizar", "automatización", "script python",
            "snippet", "fragmento de codigo", "fragmento de código",
            "sandbox", "codigo javascript", "código javascript",
        ]

    def handle(self, message: str, context: OmniaContext) -> ModuleResponse:
        text = (
            "⚙️ Detecté una petición de ejecución de código o "
            "automatización.\n\n"
            "OmniaForge (micro-entorno de ejecución local para Python "
            "y JavaScript, automatización de tareas vía instrucciones "
            "en lenguaje natural) es un proyecto independiente aún no "
            "integrado.\n\n"
            "♋ Cuando esté activo, procesaré tu fragmento de código "
            "directamente en pantalla."
        )
        return ModuleResponse(
            text=text,
            module_name=self.name,
            data={"status": "not_integrated", "domain": "code_sandbox"},
        )