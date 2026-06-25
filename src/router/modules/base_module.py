"""
* UBICACIÓN: OmniaMentis/src/router/modules/base_module.py
* PROPÓSITO: Contrato base que deben implementar todos los módulos
*            enrutables del comando `omnia -ai` (NutriVida, OmniaAthletics,
*            Corporal Verified, OmniaHabits, y futuros módulos).
* DEPENDENCIAS: ninguna (solo stdlib)
* CREADO: 2026-06-18
* ÚLTIMA MODIFICACIÓN: 2026-06-18
* ESTADO: Producción
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class ModuleResponse:
    """
    Respuesta estandarizada que todo módulo debe devolver al router.

    Attributes:
        text: Respuesta en texto plano para mostrar al usuario.
        module_name: Nombre del módulo que generó la respuesta (para logging
            y para que el dashboard pueda colorear/etiquetar la fuente).
        requires_followup: Si el módulo espera una respuesta de seguimiento
            del usuario (ej. confirmar datos antes de guardar).
        data: Payload estructurado opcional (ej. macros calculados, plan de
            entrenamiento) para que un frontend lo renderice como widget
            en vez de solo texto.
    """
    text: str
    module_name: str
    requires_followup: bool = False
    data: Optional[dict] = field(default=None)


class OmniaModule(ABC):
    """
    Contrato base para cualquier módulo enrutable desde `omnia -ai`.

    Cada módulo (NutriVida, OmniaAthletics, Corporal Verified, OmniaHabits)
    debe heredar de esta clase e implementar `keywords()` y `handle()`.
    El router (keyword_router.py) descubre e instancia automáticamente
    cualquier subclase registrada en MODULE_REGISTRY.

    Diseño deliberado: los módulos NO acceden directamente a la
    consciencia, ética o memoria de Omnia. Reciben un `OmniaContext`
    de solo lectura para mantener una separación clara de
    responsabilidades — el router orquesta, el core de Omnia mantiene
    su identidad, los módulos son utilidades especializadas.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Nombre legible del módulo (ej. 'NutriVida')."""
        raise NotImplementedError

    @abstractmethod
    def keywords(self) -> List[str]:
        """
        Lista de palabras clave (en minúsculas, sin acentos) que activan
        este módulo cuando aparecen en el mensaje del usuario.

        Ejemplo para NutriVida: ['comida', 'calorías', 'macros', 'dieta']
        """
        raise NotImplementedError

    @abstractmethod
    def handle(self, message: str, context: "OmniaContext") -> ModuleResponse:
        """
        Procesa el mensaje del usuario y devuelve una respuesta.

        Args:
            message: Mensaje original del usuario (sin modificar).
            context: Contexto de solo lectura de la sesión Omnia actual
                (nivel de consciencia, user_id, historial reciente).

        Returns:
            ModuleResponse con el texto a mostrar y metadata.
        """
        raise NotImplementedError

    def confidence(self, message: str) -> float:
        """
        Calcula qué tan seguro está este módulo de que el mensaje le
        corresponde, en base a coincidencias de keywords.

        Devuelve un valor en [0.0, 1.0]. El router usa esto para
        desambiguar cuando varios módulos podrían aplicar (ej. "calorías"
        podría ser NutriVida o OmniaAthletics).

        Las subclases pueden sobrescribir este método si necesitan lógica
        de scoring más sofisticada que el conteo simple de keywords.
        """
        text_lower = message.lower()
        matches = sum(1 for kw in self.keywords() if kw in text_lower)
        if matches == 0:
            return 0.0
        # Normalizado: más matches = más confianza, con techo en 1.0
        return min(matches / 3.0, 1.0)


@dataclass
class OmniaContext:
    """
    Contexto de solo lectura que el router pasa a cada módulo.

    Se construye una vez por petición y se pasa a `handle()`. Los
    módulos NO deben mutar este objeto ni acceder a estado interno de
    Omnia más allá de lo expuesto aquí explícitamente.
    """
    user_id: str
    consciousness_level: float
    session_id: str
    recent_messages: List[str] = field(default_factory=list)