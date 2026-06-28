"""
* UBICACIÓN: OmniaMentis/src/router/keyword_router.py
* PROPÓSITO: Router central del comando `omnia -ai`. Decide si un mensaje
*            del usuario debe ser atendido por un módulo especializado
*            (NutriVida, OmniaAthletics, Corporal Verified, OmniaHabits,
*            y futuros módulos del ecosistema) o por el núcleo
*            conversacional de Omnia Mentis.
* DEPENDENCIAS: src/router/modules/*
* CREADO: 2026-06-18
* ÚLTIMA MODIFICACIÓN: 2026-06-19
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
*
* CAMBIOS 2026-06-19 (ver docs/requisitos_nucleo_omniamentis.md
* Sección 3): el router ahora actúa como gate de autorización elevada
* para módulos marcados con requires_elevated_auth=True. El router no
* implementa el mecanismo de verificación (biometría, etc.) — recibe
* un callback `auth_checker` inyectado desde fuera, que es quien sabe
* cómo verificar la sesión actual. Si el módulo lo requiere y no hay
* auth_checker configurado, o el checker devuelve False, el router
* NUNCA invoca handle() del módulo sensible.
"""

from dataclasses import dataclass
from typing import Callable, List, Optional, Type

from .modules.base_module import OmniaModule, OmniaContext, ModuleResponse
from .modules.nutrivida import NutriVidaModule
from .modules.omnia_athletics import OmniaAthleticsModule
from .modules.corporal_verified import CorporalVerifiedModule
from .modules.omnia_habits import OmniaHabitsModule
from .modules.omnia_chronos import OmniaChronosModule
from .modules.omnia_forge import OmniaForgeModule
from .modules.omnia_studio import OmniaStudioModule
from .modules.omnia_engine import OmniaEngineModule
from .modules.omnia_core import OmniaCoreModule


# Registro central de módulos disponibles. Agregar un módulo nuevo es
# tan simple como: (1) crear la clase en modules/, heredando de
# OmniaModule, (2) importarla aquí, (3) agregarla a esta lista.
# El orden importa: en caso de empate de confianza, gana el primero.
MODULE_REGISTRY: List[Type[OmniaModule]] = [
    NutriVidaModule,
    OmniaAthleticsModule,
    CorporalVerifiedModule,
    OmniaHabitsModule,
    OmniaChronosModule,
    OmniaForgeModule,
    OmniaStudioModule,
    OmniaEngineModule,
    OmniaCoreModule,
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

# Firma del callback de verificación de autorización elevada.
# Recibe el OmniaContext de la sesión actual y devuelve True si esa
# sesión ya pasó la verificación requerida (ej. biometría) para
# acceder a módulos sensibles. El router NO sabe cómo se implementa
# esa verificación — solo la consulta.
AuthChecker = Callable[[OmniaContext], bool]


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
        auth_required_but_missing: True si el módulo con mayor
            confianza requiere autorización elevada
            (requires_elevated_auth=True) y esa autorización no se
            pudo verificar — en ese caso should_route es False y
            module_response es None, exactamente igual que si ningún
            módulo hubiera aplicado, PERO este flag permite a quien
            llama mostrar un mensaje específico de "necesitas
            verificarte" en vez de caer silenciosamente al core
            conversacional.
    """
    should_route: bool
    module_response: Optional[ModuleResponse]
    scores: dict
    auth_required_but_missing: bool = False


class KeywordRouter:
    """
    Router de palabras clave para el comando `omnia -ai`.

    Uso típico:
        router = KeywordRouter(auth_checker=mi_verificador_biometrico)
        result = router.route(user_message, context)
        if result.auth_required_but_missing:
            return "Este módulo requiere verificación biométrica primero."
        if result.should_route:
            return result.module_response.text
        else:
            return omnia_core.process_conversation(user_message)
    """

    def __init__(
        self,
        threshold: float = CONFIDENCE_THRESHOLD,
        auth_checker: Optional[AuthChecker] = None,
    ):
        """
        Args:
            threshold: umbral mínimo de confianza para enrutar.
            auth_checker: callback opcional que verifica si la sesión
                actual tiene autorización elevada. Si se omite, CUALQUIER
                módulo con requires_elevated_auth=True quedará
                permanentemente bloqueado (fail-closed, nunca
                fail-open) — es preferible que un módulo sensible no
                responda a que responda sin verificación real.
        """
        self.threshold = threshold
        self.auth_checker = auth_checker
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

        # GATE DE AUTORIZACIÓN ELEVADA — no negociable. Si el módulo
        # ganador requiere autorización elevada, handle() NUNCA se
        # invoca sin que el checker confirme explícitamente que la
        # sesión está autorizada. Fail-closed: sin checker configurado
        # equivale a "no autorizado", nunca a "autorizado por defecto".
        if best_module.requires_elevated_auth:
            authorized = bool(self.auth_checker) and self.auth_checker(context)
            if not authorized:
                return RoutingResult(
                    should_route=False,
                    module_response=None,
                    scores=scores,
                    auth_required_but_missing=True,
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