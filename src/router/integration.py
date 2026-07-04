"""
* UBICACION: OmniaMentis/src/router/integration.py
* PROPOSITO: Integracion entre KeywordRouter y el flujo de Omnia Mentis
* ESTADO: Produccion
*
* FIX 2026-06-29: set_auth_checker() ahora actualiza tambien
* _router.auth_checker, no solo la variable local _auth_checker.
* Antes el KeywordRouter se instanciaba una sola vez sin checker y
* nunca se enteraba de cambios posteriores -- el modulo quedaba
* permanentemente bloqueado aunque se inyectara un verificador valido.
"""

from typing import Any, Callable, Dict, Optional
from .keyword_router import KeywordRouter
from .modules.base_module import OmniaContext

_router = KeywordRouter()


def set_auth_checker(checker: Optional[Callable[["OmniaContext"], bool]]) -> None:
    """
    Inyecta el verificador de autorizacion elevada en el router activo.

    IMPORTANTE: actualiza _router.auth_checker directamente -- el
    KeywordRouter usa este atributo internamente en su metodo route()
    para decidir si invocar handle() en modulos con
    requires_elevated_auth=True. None = fail-closed (todos esos
    modulos quedan bloqueados).

    El checker recibe el OmniaContext completo de la peticion (no
    solo el user_id), permitiendo logica de autorizacion mas rica
    (ej. verificar sesion + nivel de consciencia + historial).
    """
    _router.auth_checker = checker


def route_or_none(
    user_message: str,
    *,
    user_id: str,
    consciousness_level: float,
    session_id: str,
) -> Optional[Dict[str, Any]]:
    """
    Intenta enrutar el mensaje a un modulo especializado.

    Returns:
        None si ningun modulo coincide.
        Dict SIEMPRE (nunca None) si un modulo coincide pero requiere
        autorizacion elevada que no se concedio -- el dict trae
        auth_required=True para que quien llama pueda informar al
        usuario, en vez de caer en silencio al core conversacional.
    """
    context = OmniaContext(
        user_id=user_id,
        consciousness_level=consciousness_level,
        session_id=session_id,
    )
    result = _router.route(user_message, context)

    # Caso 1: el router bloqueo por auth elevada faltante
    if result.auth_required_but_missing:
        blocked_name = (
            max(result.scores, key=lambda k: result.scores[k])
            if result.scores else "desconocido"
        )
        return {
            "response": (
                "🔒 Este módulo requiere verificación de identidad. "
                "Por favor, completa la verificación elevada para continuar."
            ),
            "module": blocked_name,
            "data": None,
            "auth_required": True,
        }

    # Caso 2: ningun modulo aplica -- core conversacional sigue su flujo
    if not result.should_route:
        return None

    # Caso 3: el router encontro modulo y ya esta autorizado (o no la requiere)
    module_response = result.module_response
    return {
        "response": module_response.text,
        "module": module_response.module_name,
        "data": module_response.data,
        "auth_required": False,
    }


def get_registered_modules() -> list[str]:
    """Devuelve los nombres de los modulos actualmente registrados."""
    return _router.list_modules()