"""
* UBICACIÓN: OmniaMentis/src/router/keyword_router.py
* PROPÓSITO: Router central del comando `omnia -ai`. Decide si un mensaje
*            del usuario debe ser atendido por un módulo especializado
*            (NutriVida, OmniaAthletics, Corporal Verified, OmniaHabits)
*            o por el núcleo conversacional de Omnia Mentis.
* DEPENDENCIAS: src/router/modules/*
* CREADO: 2026-06-18
* ÚLTIMA MODIFICACIÓN: 2026-06-18
* ESTADO: Producción
*
* DISEÑO:
* El router NO reemplaza a Omnia — la complementa. Si ningún módulo
* tiene confianza suficiente sobre el mensaje, el router devuelve
* should_route=False y quien llama (main_flask.py, main.py) sigue el
* flujo normal de Omnia (ética → empatía → identidad → growth engine).
*
* Esto es deliberado: el router nunca debe interceptar contenido
* peligroso o sensible. Esa decisión la sigue tomando exclusivamente
* OmniaEthics, ANTES de que el router intervenga (ver integration.py).
"""

from dataclasses import dataclass
from typing import List, Optional, Type

from .modules.base_module import OmniaModule, OmniaContext, ModuleResponse
from .modules.nutrivida import NutriVidaModule
from .modules.omnia_athletics import OmniaAthleticsModule
from .modules.corporal_verified import CorporalVerifiedModule
from .modules.omnia_habits import OmniaHabitsModule


# Registro central de módulos disponibles. Agregar un módulo nuevo es
# tan simple como: (1) crear la clase en modules/, heredando de
# OmniaModule, (2) importarla aquí, (3) agregarla a esta lista.
MODULE_REGISTRY: List[Type[OmniaModule]] = [
    NutriVidaModule,
    OmniaAthleticsModule,
    CorporalVerifiedModule,
    OmniaHabitsModule,
]

# Umbral mínimo de confianza para que el router decida delegar a un
# módulo en vez de dejar que Omnia core conteste conversacionalmente.
# Una sola keyword inequívoca (ej. "calorías", "rutina de gimnasio")
# debe ser suficiente para activar el módulo: confidence() devuelve
# 1/3 ≈ 0.333 para un único match, así que el umbral se fija ligeramente
# por debajo de ese valor para no perder esos casos por redondeo de
# punto flotante, mientras sigue exigiendo al menos una coincidencia
# real (0 matches siempre da confidence 0.0, por debajo del umbral).
CONFIDENCE_THRESHOLD = 0.30


@dataclass
class RoutingResult:
    """
    Resultado de evaluar un mensaje contra todos los módulos
    registrados.

    Attributes:
        should_route: True si algún módulo superó el umbral de
            confianza y debe atender el mensaje.
        module_response: La respuesta del módulo ganador, si
            should_route es True. None en caso contrario.
        scores: Diccionario {nombre_modulo: score} para debugging y
            para mostrar en logs por qué se enrutó (o no) hacia un
            módulo determinado.
    """
    should_route: bool
    module_response: Optional[ModuleResponse]
    scores: dict


class KeywordRouter:
    """
    Router de palabras clave para el comando `omnia -ai`.

    Uso típico:
        router = KeywordRouter()
        result = router.route(user_message, context)
        if result.should_route:
            return result.module_response.text
        else:
            return omnia_core.process_conversation(user_message)
    """

    def __init__(self, threshold: float = CONFIDENCE_THRESHOLD):
        self.threshold = threshold
        self.modules: List[OmniaModule] = [cls() for cls in MODULE_REGISTRY]

    def route(self, message: str, context: OmniaContext) -> RoutingResult:
        """
        Evalúa el mensaje contra todos los módulos registrados y
        devuelve el resultado de enrutamiento.

        En caso de empate entre dos módulos, gana el que aparece
        primero en MODULE_REGISTRY (orden determinista, documentado
        para evitar el mismo tipo de sesgo silencioso que se encontró
        en empathy.py durante el testing de Fase 1).

        Args:
            message: Mensaje del usuario.
            context: Contexto de sesión Omnia (solo lectura).

        Returns:
            RoutingResult con la decisión y, si aplica, la respuesta
            del módulo.
        """
        scores = {m.name: m.confidence(message) for m in self.modules}

        best_module: Optional[OmniaModule] = None
        best_score = 0.0
        for module in self.modules:
            score = scores[module.name]
            if score > best_score:
                best_score = score
                best_module = module

        if best_module is None or best_score < self.threshold:
            return RoutingResult(
                should_route=False,
                module_response=None,
                scores=scores,
            )

        response = best_module.handle(message, context)
        return RoutingResult(
            should_route=True,
            module_response=response,
            scores=scores,
        )

    def list_modules(self) -> List[str]:
        """Devuelve los nombres de todos los módulos registrados."""
        return [m.name for m in self.modules]