"""
* UBICACION: OmniaMentis/src/core/studio/studio.py
* PROPOSITO: Motor de OmniaStudio: paletas de color (con contraste verificado),
*            esquemas de iluminacion y prompts para imagenes. Determinista.
*            El modulo solo presenta lo que este motor calcula.
* DEPENDENCIAS: re, colorsys (stdlib)
* CREADO: 2026-10-18
* ESTADO: Produccion
*
* DECISIONES
*   - Identidad Omnia por defecto: fondo #000000 y azul electrico #00C8FF (el
*     mismo --neon-blue del panel de OmniaMentis).
*   - El contraste se calcula con la formula WCAG 2.x (luminancia relativa);
*     AA de texto normal = 4.5. No se "estima": se calcula.
*   - No se generan prompts de contenido sexual o explicito (a nadie).
*   - Un prompt no copia a artistas vivos ni a personas reales: el motor no puede
*     detectarlo, asi que lo advierte siempre en la respuesta.
*   - Estos modulos no guardan nada del usuario: no hay datos personales aqui.
"""

import colorsys
import re
from typing import Dict, List, Optional

DEFAULT_BASE = "#00C8FF"
BACKGROUND = "#000000"
MAX_SUBJECT = 200
AA_NORMAL = 4.5

_HEX = re.compile(r"#([0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b")
_BLOCK = re.compile(r"desnud|sexual|sexo|porn|er[oó]tic|nsfw|gore|fetiche", re.I)
_SUBJECT = (
    re.compile(r"(?:imagen|foto(?:graf[ií]a)?|retrato|escena|ilustraci[oó]n|portada|cartel)\s+(?:de|del|sobre)\s+(.+)$", re.I | re.S),
    re.compile(r"\bprompt(?:\s+(?:creativo|para\s+imagen|para\s+foto(?:graf[ií]a)?))?\s+(?:de|sobre)\s+(.+)$", re.I | re.S),
)
# donde termina el sujeto y empiezan las indicaciones de luz, color o estilo
_CUT = re.compile(r"\s+(?:(?:con|y|en)\s+)?(?:iluminaci[oó]n|luz|colores?|paleta|estilo)\b|\s+#|,\s*", re.I)
_GENERIC_SUBJECTS = {"foto", "fotografia", "fotografía", "imagen", "imagenes", "imágenes", "una foto", "una imagen",
                     "una fotografia", "una fotografía", "mi marca", "mi proyecto"}


class InvalidColor(ValueError):
    """Color que no es #RGB ni #RRGGBB."""


# ------------------------------------------------------------------ color
def parse_hex(text: Optional[str]) -> Optional[str]:
    """Primer #RGB / #RRGGBB del texto, normalizado a #RRGGBB mayusculas; None si no hay."""
    m = _HEX.search(text or "")
    if not m:
        return None
    h = m.group(1)
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return "#" + h.upper()


def _rgb(hex_color: str):
    if not isinstance(hex_color, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", hex_color):
        raise InvalidColor("Color no válido.")
    return tuple(int(hex_color[i:i + 2], 16) / 255 for i in (1, 3, 5))


def _to_hex(r: float, g: float, b: float) -> str:
    return "#{:02X}{:02X}{:02X}".format(*(max(0, min(255, round(v * 255))) for v in (r, g, b)))


def luminance(hex_color: str) -> float:
    def lin(c):
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (lin(c) for c in _rgb(hex_color))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(a: str, b: str) -> float:
    la, lb = luminance(a), luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return round((hi + 0.05) / (lo + 0.05), 2)


def rotate(hex_color: str, degrees: float) -> str:
    """Mismo brillo y saturacion, matiz girado."""
    h, l, s = colorsys.rgb_to_hls(*_rgb(hex_color))
    return _to_hex(*colorsys.hls_to_rgb((h + degrees / 360.0) % 1.0, l, s))


def best_text(hex_color: str) -> Dict[str, object]:
    """Texto negro o blanco, el de mayor contraste sobre `hex_color`."""
    white, black = contrast_ratio(hex_color, "#FFFFFF"), contrast_ratio(hex_color, "#000000")
    color, ratio = ("#FFFFFF", white) if white >= black else ("#000000", black)
    return {"text": color, "ratio": ratio, "aa": ratio >= AA_NORMAL}


def build_palette(base: str = DEFAULT_BASE) -> Dict[str, object]:
    _rgb(base)
    base = base.upper()
    roles = [
        ("base", base), ("complementario", rotate(base, 180)),
        ("análogo 1", rotate(base, 30)), ("análogo 2", rotate(base, -30)),
        ("tríada 1", rotate(base, 120)), ("tríada 2", rotate(base, -120)),
    ]
    colors = [{"role": r, "hex": h, "on_black": contrast_ratio(h, BACKGROUND), **{"best_text": best_text(h)}}
              for r, h in roles]
    return {"base": base, "background": BACKGROUND, "colors": colors}


# ------------------------------------------------------------------ iluminacion
_LIGHTING = {
    "tech-noir": {
        "name": "Tech-noir",
        "aliases": ["tech noir", "tech-noir", "technoir", "neon", "neón", "cyberpunk"],
        "key": "luz principal lateral y dura, con gel cian o azul",
        "fill": "casi nula; deja que las sombras se pierdan",
        "rim": "contraluz magenta o azul para separar al sujeto del fondo",
        "ratio": "8:1 o más",
        "mood": "urbano, nocturno, tenso",
        "tips": "fondo oscuro, humo o neblina para ver los haces y superficies mojadas para los reflejos",
    },
    "rembrandt": {
        "name": "Rembrandt",
        "aliases": ["rembrandt"],
        "key": "luz principal a unos 45° de lado y por encima de los ojos",
        "fill": "suave o un reflector del lado opuesto",
        "rim": "opcional",
        "ratio": "alrededor de 4:1",
        "mood": "dramático y clásico",
        "tips": "busca el pequeño triángulo de luz en la mejilla del lado en sombra",
    },
    "mariposa": {
        "name": "Mariposa (butterfly)",
        "aliases": ["mariposa", "butterfly", "paramount"],
        "key": "luz frontal y alta, justo sobre la cámara",
        "fill": "reflector bajo la barbilla",
        "rim": "opcional",
        "ratio": "alrededor de 3:1",
        "mood": "glamour, favorecedor",
        "tips": "la sombra queda bajo la nariz, con forma de mariposa",
    },
    "lateral": {
        "name": "Lateral (split)",
        "aliases": ["lateral", "split", "dividida"],
        "key": "luz a 90° del sujeto",
        "fill": "ninguna o muy tenue",
        "rim": "opcional",
        "ratio": "8:1 o más",
        "mood": "misterio y carácter",
        "tips": "una mitad del rostro queda en sombra; resalta textura",
    },
    "contraluz": {
        "name": "Contraluz (rim)",
        "aliases": ["contraluz", "rim", "backlight", "a contraluz"],
        "key": "luz detrás del sujeto, apuntando hacia la cámara",
        "fill": "reflector frontal para no perder el rostro",
        "rim": "es la luz principal: dibuja el contorno",
        "ratio": "variable; mide sobre el rostro",
        "mood": "etéreo, silueta",
        "tips": "usa visera o parasol para evitar velos en el lente",
    },
    "high-key": {
        "name": "High-key",
        "aliases": ["high key", "high-key", "luminosa", "fondo blanco"],
        "key": "luz suave y amplia (softbox grande)",
        "fill": "abundante, para casi borrar sombras",
        "rim": "luz al fondo para dejarlo blanco",
        "ratio": "2:1 o menos",
        "mood": "limpio, alegre, comercial",
        "tips": "ilumina el fondo aparte y evita que el blanco invada al sujeto",
    },
    "low-key": {
        "name": "Low-key",
        "aliases": ["low key", "low-key", "oscura", "fondo negro"],
        "key": "una sola luz dirigida y controlada",
        "fill": "ninguna",
        "rim": "opcional, muy tenue",
        "ratio": "8:1 o más",
        "mood": "intenso, nocturno",
        "tips": "aleja al sujeto del fondo y cierra la luz con banderas",
    },
}
_STYLES = {"minimalista": "composición minimalista, mucho espacio negativo", "retro": "estética retro, grano de película",
           "futurista": "estética futurista, superficies limpias", "realista": "fotorrealista", "ilustración": "ilustración digital detallada"}


def scheme_names() -> List[str]:
    return [v["name"] for v in _LIGHTING.values()]


def find_scheme(text: Optional[str]) -> Optional[Dict[str, str]]:
    t = (text or "").lower()
    best, best_len = None, 0
    for v in _LIGHTING.values():
        for alias in v["aliases"]:
            if alias in t and len(alias) > best_len:
                best, best_len = v, len(alias)
    return best


def describe_scheme(s: Dict[str, str]) -> str:
    return (f"{s['name']} — ambiente: {s['mood']}.\n"
            f"  • Luz principal: {s['key']}.\n  • Relleno: {s['fill']}.\n  • Contraluz: {s['rim']}.\n"
            f"  • Relación de luces: {s['ratio']}.\n  • Consejo: {s['tips']}.")


# ------------------------------------------------------------------ prompts
def is_blocked(text: Optional[str]) -> bool:
    return bool(_BLOCK.search(text or ""))


def extract_subject(message: Optional[str]) -> Optional[str]:
    """Sujeto del prompt (despues de «de/sobre») o None si falta o es generico."""
    text = " ".join((message or "").split())
    for rx in _SUBJECT:
        m = rx.search(text)
        if m:
            subj = _CUT.split(m.group(1), maxsplit=1)[0].strip(" .,:;¿?¡!\"'")
            subj = re.sub(r"\s+(?:con|y|en)$", "", subj, flags=re.I)
            if re.match(r"(?:iluminaci[oó]n|luz|colores?|paleta|estilo)\b", subj, re.I):
                continue   # solo indicó luz/color/estilo: falta el sujeto
            if len(subj) >= 3 and subj.lower() not in _GENERIC_SUBJECTS:
                return subj[:MAX_SUBJECT]
    return None


def _composition(subject: str) -> str:
    s = subject.lower()
    if re.search(r"retrato|persona|rostro|mujer|hombre|astronauta|ni[ñn]o|ni[ñn]a", s):
        return "plano medio, regla de tercios, profundidad de campo corta (f/1.8)"
    if re.search(r"ciudad|paisaje|calle|monta[ñn]a|edificio", s):
        return "gran angular, líneas guía hacia el punto de interés, profundidad de campo amplia"
    if re.search(r"producto|botella|reloj|zapato|taza|auricular", s):
        return "plano 3/4 o cenital, fondo limpio, sujeto centrado"
    return "regla de tercios, un punto focal claro"


def build_prompt(subject: str, scheme: Optional[Dict[str, str]] = None, palette: Optional[List[str]] = None,
                 style_text: Optional[str] = None) -> str:
    subject = " ".join((subject or "").split())[:MAX_SUBJECT]
    if len(subject) < 3:
        raise ValueError("Falta el sujeto del prompt.")
    parts = [subject]
    st = (style_text or "").lower()
    for key, frag in _STYLES.items():
        if key in st:
            parts.append(frag)
            break
    if scheme:
        parts.append(f"iluminación {scheme['name'].split(' (')[0].lower()}: {scheme['key']}, relación {scheme['ratio']}")
    if palette:
        parts.append("paleta de color " + ", ".join(palette))
    parts.append(_composition(subject))
    parts.append("alta calidad, detalle nítido")
    return ", ".join(parts)
