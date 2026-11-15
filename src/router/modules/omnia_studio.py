"""
* UBICACIÓN: OmniaMentis/src/router/modules/omnia_studio.py
* PROPÓSITO: Módulo enrutable de identidad visual, fotografía y prompts
*            creativos. NO calcula nada por su cuenta: usa el motor
*            (core/studio/studio.py) y solo presenta el resultado.
* DEPENDENCIAS: base_module.py, core/studio/studio.py
* CREADO: 2026-06-19
* ÚLTIMA MODIFICACIÓN: 2026-10-18
* ESTADO: Producción
*
* CAMBIO 2026-10-18: deja de ser un stub. Entrega paletas de color con contraste
* calculado, esquemas de iluminación y prompts para imágenes. No guarda nada del
* usuario. No genera prompts sexuales o explícitos.
"""

import logging
import re
from typing import List

from core.studio import studio as st
from .base_module import OmniaModule, OmniaContext, ModuleResponse

logger = logging.getLogger(__name__)

MODULE_NAME = "OmniaStudio"
_PROMPT = re.compile(r"\bprompt\b", re.I)
_PALETTE = re.compile(r"paleta|colores|identidad visual|branding|esquema de color", re.I)
_LIGHT = re.compile(r"ilumina|\bluz\b|\bluces\b", re.I)
REMINDER = "Evita nombres de personas reales o de artistas vivos en tus prompts."


class OmniaStudioModule(OmniaModule):

    @property
    def name(self) -> str:
        return MODULE_NAME

    def keywords(self) -> List[str]:
        return [
            "identidad visual", "prompt para imagen", "prompt creativo",
            "esquema de iluminacion", "esquema de iluminación",
            "fotografia", "fotografía", "estética", "tech noir", "tech-noir",
            "paleta de colores", "diseño visual", "branding",
            "composicion fotografica", "composición fotográfica",
            "paleta", "esquema de color", "iluminación", "iluminacion", "rembrandt",
            "contraluz", "high key", "low key",
        ]

    def _resp(self, text: str, status: str, followup: bool = False, data=None) -> ModuleResponse:
        payload = {"status": status, "domain": "visual_identity"}
        if data:
            payload.update(data)
        return ModuleResponse(text=text, module_name=self.name, requires_followup=followup, data=payload)

    def handle(self, message: str, context: OmniaContext) -> ModuleResponse:
        text = message or ""
        if st.is_blocked(text):
            return self._resp("No genero prompts ni imágenes de contenido sexual o explícito. "
                              "Puedo ayudarte con otra idea visual, una paleta o un esquema de iluminación.",
                              "blocked")
        if _PROMPT.search(text):
            return self._prompt(text, context)
        if _PALETTE.search(text):
            return self._palette(text, context)
        if _LIGHT.search(text) or st.find_scheme(text):
            return self._lighting(text, context)
        return self._menu()

    def _menu(self) -> ModuleResponse:
        return self._resp(
            "Con OmniaStudio puedo:\n"
            "• Armar una paleta de color: «paleta para #FF5500» (sin color uso el azul eléctrico de Omnia).\n"
            "• Explicar un esquema de iluminación: " + ", ".join(st.scheme_names()) + ".\n"
            "• Escribir un prompt para imagen: «prompt para imagen de un faro en una tormenta con iluminación tech-noir».",
            "menu", followup=True)

    def _palette(self, text: str, context: OmniaContext) -> ModuleResponse:
        base = st.parse_hex(text) or st.DEFAULT_BASE
        pal = st.build_palette(base)
        lines = [f"Paleta a partir de {pal['base']} sobre fondo {pal['background']}:"]
        for c in pal["colors"]:
            t = c["best_text"]
            lines.append(f"  • {c['role']}: {c['hex']} — contraste sobre negro {c['on_black']}:1; "
                         f"texto {'blanco' if t['text'] == '#FFFFFF' else 'negro'} encima = {t['ratio']}:1 "
                         f"({'cumple' if t['aa'] else 'NO cumple'} AA para texto normal)")
        lines.append("El contraste se calcula con la fórmula WCAG; para texto normal el mínimo AA es 4.5:1.")
        return self._resp("\n".join(lines), "palette", data={"palette": pal, "saved": self._save(context, "paleta", {"base": pal["base"]})})

    def _lighting(self, text: str, context: OmniaContext) -> ModuleResponse:
        scheme = st.find_scheme(text)
        if scheme is None:
            return self._resp("Esquemas de iluminación que conozco: " + ", ".join(st.scheme_names())
                              + ". Dime cuál quieres, por ejemplo «iluminación tech-noir».",
                              "lighting_list", followup=True)
        return self._resp(st.describe_scheme(scheme), "lighting",
                          data={"scheme": scheme["name"], "saved": self._save(context, "iluminacion", {"scheme": scheme["name"]})})

    def _prompt(self, text: str, context: OmniaContext) -> ModuleResponse:
        subject = st.extract_subject(text)
        if subject is None:
            return self._resp("Dime el sujeto del prompt, por ejemplo: «prompt para imagen de un astronauta en una ciudad lluviosa». "
                              "Puedes añadir una iluminación (tech-noir, rembrandt…) o colores (#00C8FF).",
                              "needs_subject", followup=True)
        if st.is_blocked(subject):  # defensa extra: el sujeto ya se revisó arriba con todo el texto
            return self._resp("No genero prompts de contenido sexual o explícito.", "blocked")
        scheme = st.find_scheme(text)
        hexes = re.findall(r"#[0-9a-fA-F]{3,6}\b", text)
        palette = []
        for h in hexes[:4]:
            norm = st.parse_hex(h)
            if norm and norm not in palette:
                palette.append(norm)
        prompt = st.build_prompt(subject, scheme, palette or None, text)
        return self._resp(f"Prompt:\n{prompt}\n\n{REMINDER}", "prompt",
                          data={"prompt": prompt, "scheme": scheme["name"] if scheme else None,
                                "saved": self._save(context, "prompt", {"scheme": scheme["name"] if scheme else None})})

    def _save(self, context: OmniaContext, kind: str, payload: dict) -> bool:
        """Guarda solo QUÉ se pidió (tipo y esquema), nunca el texto de la persona."""
        if context.data_store is None:
            return False
        try:
            context.data_store.add(context.user_id, self.name, kind, payload)
            return True
        except Exception as exc:
            logger.warning("OmniaStudio: no se pudo guardar (%s): %s", kind, exc)
            return False
