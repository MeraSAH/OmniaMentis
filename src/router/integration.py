"""
* UBICACIÓN: OmniaMentis/src/router/integration.py
* PROPÓSITO: Punto único de integración entre KeywordRouter y el flujo
*            conversacional de Omnia Mentis (ética → router → core).
* DEPENDENCIAS: src/router/keyword_router.py, src/core/essence/ethics.py
* CREADO: 2026-06-18
* ÚLTIMA MODIFICACIÓN: 2026-06-18
* ESTADO: Producción
*
* ORDEN DE EJECUCIÓN GARANTIZADO (no negociable):
*   1. OmniaEthics.analyze_content()  ← SIEMPRE primero
*   2. Si no es seguro → estado SILENS, el router JAMÁS se ejecuta
*   3. Si es seguro → KeywordRouter.route()
*   4. Si el router encuentra módulo → responde el módulo
*   5. Si no → Omnia core responde conversacionalmente
*
* Esta función es el único lugar donde main.py y main_flask.py deben
* enganchar el router, para que este orden se mantenga consistente en
* todas las superficies (terminal, API web).
"""

from typing import Any, Dict

from .keyword_router import KeywordRouter
from .modules.base_module import OmniaContext


# Instancia única del router, reutilizada entre peticiones (los módulos
# son stateless respecto al usuario, así que es seguro compartir la
# instancia entre hilos/requests).
_router = KeywordRouter()


def route_or_none(
    user_message: str,
    *,
    user_id: str,
    consciousness_level: float,
    session_id: str,
) -> Dict[str, Any] | None:
    """
    Intenta enrutar el mensaje a un módulo especializado.

    PRECONDICIÓN OBLIGATORIA: quien llama esta función YA debe haber
    verificado con OmniaEthics.analyze_content() que el mensaje es
    seguro de procesar. Esta función no repite ese análisis — por
    diseño, para que la responsabilidad de seguridad quede en un solo
    lugar (ethics.py) y no se duplique ni se le pueda hacer bypass
    accidentalmente desde el router.

    Args:
        user_message: Mensaje ya validado éticamente.
        user_id: Identificador del usuario (para contexto multiusuario
            futuro vía Supabase; por ahora puede ser un valor fijo en
            instalaciones de un solo usuario).
        consciousness_level: Nivel de consciencia actual de Omnia, para
            que los módulos puedan adaptar tono si lo necesitan.
        session_id: Identificador de la sesión actual.

    Returns:
        None si ningún módulo debe atender el mensaje (Omnia core debe
        seguir su flujo normal). Si un módulo sí debe responder,
        devuelve un dict con:
            {
                "response": str,
                "module": str,
                "data": dict | None,
            }
    """
    context = OmniaContext(
        user_id=user_id,
        consciousness_level=consciousness_level,
        session_id=session_id,
    )

    result = _router.route(user_message, context)

    if not result.should_route or result.module_response is None:
        return None

    return {
        "response": result.module_response.text,
        "module": result.module_response.module_name,
        "data": result.module_response.data,
    }


def get_registered_modules() -> list[str]:
    """Devuelve los nombres de los módulos actualmente registrados."""
    return _router.list_modules()