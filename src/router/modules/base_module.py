"""
* UBICACION: OmniaMentis/src/router/modules/base_module.py
* PROPOSITO: Contrato base para todos los modulos enrutables de omnia -ai
* ESTADO: Produccion
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class ModuleResponse:
    """Respuesta estandarizada de cada modulo."""
    text: str
    module_name: str
    requires_followup: bool = False
    data: Optional[dict] = field(default=None)
    widget_type: Optional[str] = field(default=None)
    widget_payload: Optional[dict] = field(default=None)


class OmniaModule(ABC):
    """Contrato base para cualquier modulo enrutable."""

    @property
    @abstractmethod
    def name(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def keywords(self) -> List[str]:
        raise NotImplementedError

    @abstractmethod
    def handle(self, message: str, context: "OmniaContext") -> ModuleResponse:
        raise NotImplementedError

    @property
    def requires_elevated_auth(self) -> bool:
        """Por defecto False — solo Corporal Verified lo sobreescribe a True."""
        return False

    def confidence(self, message: str) -> float:
        text_lower = message.lower()
        matches = sum(1 for kw in self.keywords() if kw in text_lower)
        if matches == 0:
            return 0.0
        return min(matches / 3.0, 1.0)


@dataclass
class OmniaContext:
    """Contexto de solo lectura que el router pasa a cada modulo."""
    user_id: str
    consciousness_level: float
    session_id: str
    recent_messages: List[str] = field(default_factory=list)