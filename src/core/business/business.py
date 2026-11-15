"""
* UBICACION: OmniaMentis/src/core/business/business.py
* PROPOSITO: Motor de OmniaEngine: cotizaciones (subtotal, descuento, IVA, total) y
*            analisis de embudos de venta (conversion por etapa, CAC, retorno).
*            Aritmetica exacta con Decimal; el modulo solo presenta el resultado.
* DEPENDENCIAS: decimal, re (stdlib)
* CREADO: 2026-10-20
* ESTADO: Produccion
*
* DECISIONES
*   - Dinero con Decimal y redondeo ROUND_HALF_UP a centavos; nunca float.
*   - Moneda: dolares (USD). IVA por defecto 15 % (SUPUESTO que se declara siempre en
*     la respuesta: la tarifa puede cambiar; se corrige con «iva 12%», etc.).
*   - Limites duros: 50 lineas por cotizacion, cantidades hasta 1 000 000, importes
*     hasta 1 000 000 000, nombres de 60 caracteres, embudo de 2 a 8 etapas.
*   - No se inventan cifras: si faltan datos se pide el formato; un embudo cuyas
*     etapas crecen se informa como advertencia, no se «arregla».
*   - No es asesoria contable ni tributaria.
"""

import re
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from typing import Any, Dict, List, Optional

DEFAULT_VAT_PERCENT = Decimal("15")
MAX_ITEMS = 50
MAX_QTY = Decimal("1000000")
MAX_AMOUNT = Decimal("1000000000")
MAX_NAME = 60
MIN_STAGES, MAX_STAGES = 2, 8
CENT = Decimal("0.01")

_NUM = r"\d+(?:[.,]\d+)?"
_VAT = re.compile(r"\biva\s*(?:del?\s*)?(" + _NUM + r")\s*%?", re.I)
_DISCOUNT = re.compile(r"\bdescuento\s*(?:del?\s*)?(" + _NUM + r")\s*%", re.I)
# «concepto: 3 x 120», «concepto 120», «concepto: $1.200,50» (se acepta coma o punto decimal)
_ITEM = re.compile(r"^\s*(?P<name>[^\d$:=][^:=$\d]*?)\s*[:=]?\s*(?:(?P<qty>" + _NUM + r")\s*[x×]\s*)?\$?\s*(?P<price>" + _NUM + r")\s*$", re.I)
_STAGE = re.compile(r"(?P<name>[A-Za-zÁÉÍÓÚáéíóúÑñ][A-Za-zÁÉÍÓÚáéíóúÑñ ]{1,29}?)\s*[:=]?\s*(?P<n>\d+(?:[.,]\d+)?)", re.I)
_META = {"inversion": "investment", "inversión": "investment", "gasto": "investment", "ticket": "ticket", "precio": "ticket"}


class InvalidInput(ValueError):
    """Datos fuera de rango o con formato no reconocido."""


def _dec(text: str) -> Decimal:
    t = text.strip()
    if "," in t and "." in t:                       # 1.200,50 -> 1200.50 / 1,200.50 -> 1200.50
        t = t.replace(".", "").replace(",", ".") if t.rfind(",") > t.rfind(".") else t.replace(",", "")
    else:
        t = t.replace(",", ".")
    try:
        d = Decimal(t)
    except InvalidOperation:
        raise InvalidInput("Número no válido.") from None
    if not d.is_finite():
        raise InvalidInput("Número no válido.")
    return d


def money(d: Decimal) -> Decimal:
    return d.quantize(CENT, rounding=ROUND_HALF_UP)


def fmt_money(d: Decimal) -> str:
    return f"${money(d):,.2f}"


# ------------------------------------------------------------------ cotizacion
def parse_percent(pattern: "re.Pattern", text: str, default: Optional[Decimal]) -> Optional[Decimal]:
    m = pattern.search(text or "")
    if not m:
        return default
    p = _dec(m.group(1))
    if p < 0 or p > 100:
        raise InvalidInput("Un porcentaje debe estar entre 0 y 100.")
    return p


def parse_items(text: str):
    """Lineas «concepto: [cantidad x] precio» separadas por ; , (con espacio) o saltos de linea.
    Devuelve (items, ignorados): lo que no se entiende se REPORTA, nunca se descarta en silencio."""
    body = _VAT.sub("", _DISCOUNT.sub("", text or ""))
    # quitar el encabezado «... cotización de / presupuesto para ...:» (solo la palabra clave y su preposicion)
    body = re.sub(r"^.*?\b(?:cotiz\w*|presupuesto)\b(?:\s+(?:de|del|para|por))?\s*[:;]?\s*", "", body, count=1, flags=re.I | re.S)
    items: List[Dict[str, Any]] = []
    ignored: List[str] = []
    for chunk in re.split(r"[;\n]+|,\s+", body):
        chunk = chunk.strip(" ,.")
        if not chunk:
            continue
        m = _ITEM.match(chunk)
        name = " ".join(m.group("name").split())[:MAX_NAME].strip(" -,") if m else ""
        if not m or not name:
            ignored.append(chunk[:MAX_NAME])
            continue
        qty = _dec(m.group("qty")) if m.group("qty") else Decimal(1)
        items.append({"name": name, "qty": qty, "unit_price": _dec(m.group("price"))})
    return items, ignored


def build_quote(items: List[Dict[str, Any]], vat_percent: Decimal = DEFAULT_VAT_PERCENT,
                discount_percent: Decimal = Decimal(0)) -> Dict[str, Any]:
    if not items:
        raise InvalidInput("La cotización no tiene conceptos.")
    if len(items) > MAX_ITEMS:
        raise InvalidInput(f"Máximo {MAX_ITEMS} conceptos por cotización.")
    for p in (vat_percent, discount_percent):
        if p < 0 or p > 100:
            raise InvalidInput("Un porcentaje debe estar entre 0 y 100.")
    lines = []
    subtotal = Decimal(0)
    for it in items:
        qty, price = it["qty"], it["unit_price"]
        if qty <= 0 or qty > MAX_QTY:
            raise InvalidInput(f"Cantidad no válida en «{it['name']}».")
        if price < 0 or price > MAX_AMOUNT:
            raise InvalidInput(f"Precio no válido en «{it['name']}».")
        line_total = money(qty * price)
        if line_total > MAX_AMOUNT:
            raise InvalidInput(f"El importe de «{it['name']}» es demasiado grande.")
        subtotal += line_total
        lines.append({"name": it["name"], "qty": qty, "unit_price": money(price), "total": line_total})
    if subtotal > MAX_AMOUNT:
        raise InvalidInput("El total es demasiado grande.")
    discount = money(subtotal * discount_percent / 100)
    base = subtotal - discount
    vat = money(base * vat_percent / 100)
    return {"lines": lines, "subtotal": money(subtotal), "discount_percent": discount_percent, "discount": discount,
            "base": money(base), "vat_percent": vat_percent, "vat": vat, "total": money(base + vat), "currency": "USD"}


def format_quote(q: Dict[str, Any], vat_assumed: bool) -> str:
    out = ["Cotización:"]
    for l in q["lines"]:
        qty = f"{l['qty'].normalize():f}"
        out.append(f"  • {l['name']}: {qty} × {fmt_money(l['unit_price'])} = {fmt_money(l['total'])}")
    out.append(f"Subtotal: {fmt_money(q['subtotal'])}")
    if q["discount"] > 0:
        out.append(f"Descuento ({q['discount_percent'].normalize():f} %): -{fmt_money(q['discount'])}")
        out.append(f"Base imponible: {fmt_money(q['base'])}")
    out.append(f"IVA ({q['vat_percent'].normalize():f} %): {fmt_money(q['vat'])}")
    out.append(f"TOTAL: {fmt_money(q['total'])} USD")
    if vat_assumed:
        out.append(f"Supuse IVA {DEFAULT_VAT_PERCENT} %: si la tarifa es otra, dime «iva 12%» (o la que corresponda).")
    out.append("Es un cálculo de apoyo, no asesoría contable ni tributaria.")
    return "\n".join(out)


def quote_summary(q: Dict[str, Any]) -> Dict[str, Any]:
    """Resumen JSON-serializable para guardar (sin Decimal)."""
    return {"lines": [{"name": l["name"], "qty": float(l["qty"]), "unit_price": float(l["unit_price"]),
                       "total": float(l["total"])} for l in q["lines"]],
            "subtotal": float(q["subtotal"]), "discount": float(q["discount"]), "vat_percent": float(q["vat_percent"]),
            "vat": float(q["vat"]), "total": float(q["total"]), "currency": q["currency"]}


# ------------------------------------------------------------------ embudo
def parse_funnel(text: str) -> Dict[str, Any]:
    """Etapas «nombre numero» y metadatos (inversion, ticket) de un texto libre."""
    stages: List[Dict[str, Any]] = []
    meta: Dict[str, Decimal] = {}
    for m in _STAGE.finditer(text or ""):
        name = " ".join(m.group("name").split()).strip()
        low = name.lower()
        key = None
        for word, field in _META.items():
            if low.endswith(word):
                key = field
        if key:
            meta.setdefault(key, _dec(m.group("n")))
            continue
        # quitar muletillas iniciales («mi embudo», «analiza», «tengo»…)
        name = re.sub(r"^(?:analiza|analizar|mi|el|un|una|embudo|de|con|tengo|tuve|y)\s+", "", name, flags=re.I).strip()
        name = re.sub(r"^(?:embudo|de|con|y)\s+", "", name, flags=re.I).strip()
        if len(name) < 2:
            continue
        stages.append({"name": name[:MAX_NAME], "count": _dec(m.group("n"))})
    return {"stages": stages, "meta": meta}


def analyze_funnel(stages: List[Dict[str, Any]], investment: Optional[Decimal] = None,
                   ticket: Optional[Decimal] = None) -> Dict[str, Any]:
    if not (MIN_STAGES <= len(stages) <= MAX_STAGES):
        raise InvalidInput(f"Un embudo necesita entre {MIN_STAGES} y {MAX_STAGES} etapas con su cantidad.")
    for s in stages:
        if s["count"] < 0 or s["count"] > MAX_AMOUNT:
            raise InvalidInput(f"Cantidad no válida en «{s['name']}».")
    for label, v in (("inversión", investment), ("ticket", ticket)):
        if v is not None and (v < 0 or v > MAX_AMOUNT):
            raise InvalidInput(f"Valor no válido en {label}.")
    first = stages[0]["count"]
    rows, warnings = [], []
    worst = None
    for i, s in enumerate(stages):
        row = {"name": s["name"], "count": s["count"],
               "from_start_pct": (s["count"] / first * 100).quantize(Decimal("0.1"), ROUND_HALF_UP) if first > 0 else None,
               "from_previous_pct": None}
        if i > 0:
            prev = stages[i - 1]["count"]
            if prev > 0:
                step = s["count"] / prev * 100
                row["from_previous_pct"] = step.quantize(Decimal("0.1"), ROUND_HALF_UP)
                if s["count"] > prev:
                    warnings.append(f"«{s['name']}» ({s['count']:f}) es mayor que «{stages[i-1]['name']}» ({prev:f}): revisa los datos.")
                elif worst is None or step < worst[1]:
                    worst = (i, step)
        rows.append(row)
    out: Dict[str, Any] = {"stages": rows, "warnings": warnings, "worst_step": None}
    if worst is not None:
        out["worst_step"] = {"from": stages[worst[0] - 1]["name"], "to": stages[worst[0]]["name"],
                             "pct": worst[1].quantize(Decimal("0.1"), ROUND_HALF_UP)}
    last = stages[-1]["count"]
    if investment is not None and last > 0:
        out["cac"] = money(investment / last)
    if ticket is not None:
        revenue = money(last * ticket)
        out["revenue"] = revenue
        if investment is not None and investment > 0:
            out["roi_pct"] = ((revenue - investment) / investment * 100).quantize(Decimal("0.1"), ROUND_HALF_UP)
    return out


def format_funnel(r: Dict[str, Any]) -> str:
    out = ["Embudo:"]
    for row in r["stages"]:
        prev = f" · {row['from_previous_pct']:f} % de la etapa anterior" if row["from_previous_pct"] is not None else ""
        start = f" ({row['from_start_pct']:f} % del inicio)" if row["from_start_pct"] is not None else ""
        out.append(f"  • {row['name']}: {row['count'].normalize():f}{start}{prev}")
    w = r["worst_step"]
    if w:
        out.append(f"Mayor caída: de «{w['from']}» a «{w['to']}» (solo pasa el {w['pct']:f} %). Ahí está la mejor oportunidad de mejora.")
    if "cac" in r:
        out.append(f"Costo por cliente (CAC): {fmt_money(r['cac'])}")
    if "revenue" in r:
        out.append(f"Ingresos estimados: {fmt_money(r['revenue'])}")
    if "roi_pct" in r:
        out.append(f"Retorno sobre la inversión: {r['roi_pct']:f} %")
    out.extend("⚠ " + w for w in r["warnings"])
    out.append("Son cálculos sobre las cifras que me diste; no predicen resultados futuros.")
    return "\n".join(out)


def funnel_summary(r: Dict[str, Any]) -> Dict[str, Any]:
    return {"stages": [{"name": x["name"], "count": float(x["count"])} for x in r["stages"]],
            "cac": float(r["cac"]) if "cac" in r else None, "revenue": float(r["revenue"]) if "revenue" in r else None,
            "roi_pct": float(r["roi_pct"]) if "roi_pct" in r else None}
