"""
* UBICACION: OmniaMentis/src/router/integration.py
* PROPOSITO: Integracion entre KeywordRouter y el flujo de Omnia Mentis
* ESTADO: Produccion
"""

from typing import Any, Callable, Dict, Optional
from .keyword_router import KeywordRouter
from .modules.base_module import OmniaContext

_router = KeywordRouter()
_auth_checker = None


def set_auth_checker(checker):
    """Inyecta el verificador de autorizacion elevada."""
    global _auth_checker
    _auth_checker = checker


def route_or_none(user_message, *, user_id, consciousness_level, session_id):
    """Intenta enrutar el mensaje a un modulo especializado."""
    context = OmniaContext(
        user_id=user_id,
        consciousness_level=consciousness_level,
        session_id=session_id,
    )
    result = _router.route(user_message, context)

    if not result.should_route or result.module_response is None:
        return None

    module_response = result.module_response

    matched_module = next(
        (m for m in _router.modules if m.name == module_response.module_name),
        None,
    )
    if matched_module and matched_module.requires_elevated_auth:
        if _auth_checker is None or not _auth_checker(user_id):
            return {
                "response": "Este modulo requiere autorizacion elevada.",
                "module": module_response.module_name,
                "data": None,
                "auth_required": True,
            }

    return {
        "response": module_response.text,
        "module": module_response.module_name,
        "data": module_response.data,
        "auth_required": False,
    }


def get_registered_modules():
    """Devuelve los nombres de los modulos registrados."""
    return _router.list_modules()