"""
* UBICACIÓN: OmniaMentis/src/router/modules/omnia_forge.py
* PROPÓSITO: Módulo enrutable de código. REVISA código Python sin ejecutarlo
*            (core/forge/code_review.py) y explica por qué no ejecuta nada en el
*            servidor. Solo presenta lo que calcula el motor.
* DEPENDENCIAS: base_module.py, core/forge/code_review.py
* CREADO: 2026-06-19
* ÚLTIMA MODIFICACIÓN: 2026-10-20
* ESTADO: Producción
*
* DECISIÓN DE SEGURIDAD (2026-10-20): OmniaForge NO ejecuta código en el servidor.
* El stub original pedía un sandbox aislado; ese aislamiento no existe en este
* despliegue y simularlo sería engañar. La revisión estática sí funciona y no
* ejecuta nada. La ejecución queda para la aplicación de escritorio (en el equipo
* de la propia persona). Acceso solo adultos (policy.py).
*
* Por el chat entran fragmentos cortos (límite de 1000 caracteres, una línea de
* escritura). Para código largo existe POST /api/forge/review (hasta 20 000
* caracteres).
"""

import logging
import re
from typing import List

from core.forge import code_review as cr
from .base_module import OmniaModule, OmniaContext, ModuleResponse

logger = logging.getLogger(__name__)

MODULE_NAME = "OmniaForge"
_RUN = re.compile(r"ejecut|correr|corre |run\b|sandbox", re.I)
NO_EXEC = ("No ejecuto código en el servidor de OmniaMentis: un servidor compartido no puede aislarlo con garantías, "
           "y fingirlo sería engañarte. Lo que sí hago es revisarlo SIN ejecutarlo (errores de sintaxis, llamadas peligrosas, "
           "secretos escritos en el código, complejidad). La ejecución local llegará con la aplicación de escritorio.")


class OmniaForgeModule(OmniaModule):

    @property
    def name(self) -> str:
        return MODULE_NAME

    def keywords(self) -> List[str]:
        return [
            "ejecutar codigo", "ejecutar código", "correr script",
            "automatizar", "automatización", "script python",
            "snippet", "fragmento de codigo", "fragmento de código",
            "sandbox", "codigo javascript", "código javascript",
            "revisar codigo", "revisar código", "revisa este codigo", "revisa este código",
        ]

    def _resp(self, text: str, status: str, followup: bool = False, data=None) -> ModuleResponse:
        payload = {"status": status, "domain": "code_review"}
        if data:
            payload.update(data)
        return ModuleResponse(text=text, module_name=self.name, requires_followup=followup, data=payload)

    def handle(self, message: str, context: OmniaContext) -> ModuleResponse:
        text = message or ""
        lang, code = cr.extract_code(text)
        wants_run = bool(_RUN.search(text))

        if code is None:
            body = (NO_EXEC + "\n\nPara revisar algo, envíalo entre ``` ```, por ejemplo:\n"
                    "revisa este código ```python\nprint('hola')\n```\n"
                    "(El chat admite 1000 caracteres; para código más largo usa la revisión por API.)")
            return self._resp(body, "needs_code" if not wants_run else "no_execution", followup=True)

        language = cr.normalize_language(lang)
        if language != "python":
            return self._resp("Por ahora solo reviso Python. " + NO_EXEC, "unsupported_language",
                              data={"language": language})
        try:
            result = cr.review(code)
        except cr.ReviewError as exc:
            return self._resp(str(exc), "invalid_input", followup=True)
        out = cr.format_review(result)
        if wants_run:
            out = NO_EXEC + "\n\n" + out
        saved = self._save(context, result)
        return self._resp(out, "reviewed" if result["valid"] else "syntax_error",
                          data={"valid": result["valid"], "findings": result.get("findings_total", 0),
                                "metrics": result.get("metrics"), "saved": saved})

    def _save(self, context: OmniaContext, result: dict) -> bool:
        """Guarda SOLO un resumen numérico de la revisión; nunca el código de la persona."""
        if context.data_store is None:
            return False
        payload = cr.summary(result)
        try:
            context.data_store.add(context.user_id, self.name, "revision", payload)
            return True
        except Exception as exc:
            logger.warning("OmniaForge: no se pudo guardar el resumen: %s", exc)
            return False
