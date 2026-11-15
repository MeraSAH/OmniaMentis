"""
* UBICACIÓN: OmniaMentis/src/router/modules/omnia_engine.py
* PROPÓSITO: Módulo enrutable de negocio. NO calcula nada por su cuenta: usa el
*            motor (core/business/business.py) y guarda en el almacén único que
*            le entrega el contexto. Solo presenta el resultado.
* DEPENDENCIAS: base_module.py, core/business/business.py
* CREADO: 2026-06-19
* ÚLTIMA MODIFICACIÓN: 2026-10-20
* ESTADO: Producción
*
* CAMBIO 2026-10-20: deja de ser un stub. Hace cotizaciones (subtotal, descuento,
* IVA, total) y analiza embudos de venta (conversión, CAC, ingresos, ROI). Los bots
* de atención, el CRM y la automatización de procesos NO existen todavía (necesitan
* integraciones externas) y el módulo lo dice en vez de simularlos. Solo adultos
* (policy.py).
"""

import logging
import re
from decimal import Decimal
from typing import List

from core.business import business as biz
from .base_module import OmniaModule, OmniaContext, ModuleResponse

logger = logging.getLogger(__name__)

MODULE_NAME = "OmniaEngine"
_QUOTE = re.compile(r"cotiz|presupuesto", re.I)
_FUNNEL = re.compile(r"embudo|funnel|pipeline", re.I)
QUOTE_EXAMPLE = "cotiza: diseño web: 1 x 500; hosting anual: 12 x 10,50; logo: 120 descuento 10% iva 15%"
FUNNEL_EXAMPLE = "embudo: visitas 1000, leads 100, clientes 10, inversión 500, ticket 80"


class OmniaEngineModule(OmniaModule):

    @property
    def name(self) -> str:
        return MODULE_NAME

    def keywords(self) -> List[str]:
        return [
            "embudo de venta", "sales funnel", "funnel",
            "bot de atencion", "bot de atención", "automatizar ventas",
            "cotizacion", "cotización", "presupuesto proyecto",
            "captacion de clientes", "captación de clientes",
            "seguimiento de leads", "crm", "pipeline de ventas",
            "automatizacion de negocio", "automatización de negocio",
            "cotiza", "embudo",
        ]

    def _resp(self, text: str, status: str, followup: bool = False, data=None) -> ModuleResponse:
        payload = {"status": status, "domain": "business"}
        if data:
            payload.update(data)
        return ModuleResponse(text=text, module_name=self.name, requires_followup=followup, data=payload)

    def _save(self, context: OmniaContext, kind: str, payload: dict) -> bool:
        if context.data_store is None:
            return False
        try:
            context.data_store.add(context.user_id, self.name, kind, payload)
            return True
        except Exception as exc:  # el cálculo sigue valiendo aunque no se guarde
            logger.warning("OmniaEngine: no se pudo guardar (%s): %s", kind, exc)
            return False

    def handle(self, message: str, context: OmniaContext) -> ModuleResponse:
        text = message or ""
        if _QUOTE.search(text):
            return self._quote(text, context)
        if _FUNNEL.search(text):
            return self._funnel(text, context)
        return self._menu()

    def _menu(self) -> ModuleResponse:
        return self._resp(
            "Con OmniaEngine puedo, hoy:\n"
            f"• Hacer una cotización con descuento e IVA. Ejemplo: «{QUOTE_EXAMPLE}»\n"
            f"• Analizar un embudo de ventas. Ejemplo: «{FUNNEL_EXAMPLE}»\n"
            "Los bots de atención, el CRM y la automatización de procesos todavía no existen: necesitan conectarse a "
            "servicios externos (WhatsApp, correo, tu CRM) y no voy a simularlos.",
            "menu", followup=True)

    def _quote(self, text: str, context: OmniaContext) -> ModuleResponse:
        try:
            items, ignored = biz.parse_items(text)
            vat = biz.parse_percent(biz._VAT, text, None)
            discount = biz.parse_percent(biz._DISCOUNT, text, Decimal(0))
            if not items:
                return self._resp(f"Dime los conceptos así: «{QUOTE_EXAMPLE}»", "needs_items", followup=True,
                                  data={"ignored": ignored})
            quote = biz.build_quote(items, vat if vat is not None else biz.DEFAULT_VAT_PERCENT, discount)
        except biz.InvalidInput as exc:
            return self._resp(f"No pude hacer la cotización: {exc} Formato: «{QUOTE_EXAMPLE}»", "invalid_input", followup=True)
        out = biz.format_quote(quote, vat_assumed=vat is None)
        if ignored:
            out += "\nNo entendí estas partes y NO las incluí: " + "; ".join(f"«{x}»" for x in ignored) + "."
        summary = biz.quote_summary(quote)
        saved = self._save(context, "cotizacion", summary)
        return self._resp(out, "quoted", followup=bool(ignored),
                          data={"total": summary["total"], "currency": "USD", "ignored": ignored, "saved": saved})

    def _funnel(self, text: str, context: OmniaContext) -> ModuleResponse:
        try:
            parsed = biz.parse_funnel(text)
            result = biz.analyze_funnel(parsed["stages"], parsed["meta"].get("investment"), parsed["meta"].get("ticket"))
        except biz.InvalidInput as exc:
            return self._resp(f"No pude analizar el embudo: {exc} Formato: «{FUNNEL_EXAMPLE}»", "invalid_input", followup=True)
        summary = biz.funnel_summary(result)
        saved = self._save(context, "embudo", summary)
        return self._resp(biz.format_funnel(result), "funnel", data={"summary": summary, "saved": saved})
