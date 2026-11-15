"""
* UBICACIÓN: OmniaMentis/src/router/modules/omnia_core.py
* PROPÓSITO: Módulo enrutable para optimización de hardware, rendimiento
*            del dispositivo y compilación Edge/Cloud híbrida.
* DEPENDENCIAS: src/router/modules/base_module.py
* CREADO: 2026-06-19
* ÚLTIMA MODIFICACIÓN: 2026-06-19
* ESTADO: Producción (routing); la medición del dispositivo vive en el dashboard (cliente)
*
* NOTA DE NOMENCLATURA: OmniaCore (módulo de optimización de hardware)
* es distinto de OmniaMentis (núcleo de IA conversacional). El primero
* es una herramienta del ecosistema Omnia que gestiona recursos del
* dispositivo; el segundo es el cerebro central del sistema. El nombre
* puede generar confusión — se documenta explícitamente aquí para
* que cualquier desarrollador que lo vea sepa que son proyectos
* con responsabilidades completamente distintas.
"""

from typing import List
from .base_module import OmniaModule, OmniaContext, ModuleResponse


class OmniaCoreModule(OmniaModule):
    """
    Captura peticiones relacionadas con rendimiento del dispositivo,
    optimización de recursos, tasa de refresco y delegación de cálculos
    a microservicios cuando el hardware es limitado.

    DIFERENCIA CON OMNIAMENTIS: OmniaCore gestiona HARDWARE (CPU/GPU,
    FPS, memoria activa, Edge/Cloud híbrido). OmniaMentis gestiona
    CONVERSACIÓN e IDENTIDAD. Dos dominios completamente separados.
    """

    @property
    def name(self) -> str:
        return "OmniaCore"

    def keywords(self) -> List[str]:
        return [
            "rendimiento del dispositivo", "optimizar hardware",
            "fps", "tasa de refresco", "memoria activa",
            "edge computing", "cloud computing", "delegacion de calculo",
            "delegación de cálculo", "microservicio", "optimizar rendimiento",
            "recursos del sistema", "cpu", "gpu", "lag", "lentitud",
        ]

    def handle(self, message: str, context: OmniaContext) -> ModuleResponse:
        text = (
            "💻 OmniaCore vive en tu pantalla, no en el servidor: el servidor no puede ver tu dispositivo.\n\n"
            "Ábrelo en ▦ MÓDULOS → OmniaCore: mide los núcleos, la memoria y los FPS reales de tu navegador, "
            "te da un nivel (alto, medio o ahorro) y reduce animaciones y desenfoques si tu equipo va justo. "
            "Puedes elegir el modo a mano.\n\n"
            "Todavía no existe la delegación de cálculos a microservicios (Edge/Cloud)."
        )
        return ModuleResponse(
            text=text,
            module_name=self.name,
            data={"status": "client_side", "domain": "hardware_optimization"},
        )