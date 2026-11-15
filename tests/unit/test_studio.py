# tests/unit/test_studio.py
"""
* UBICACIÓN: OmniaMentis/tests/unit/test_studio.py
* PROPÓSITO: Tests del motor de OmniaStudio (src/core/studio/studio.py) y del módulo.
* CREADO: 2026-10-18
* ESTADO: Test Permanente
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from core.studio import studio as st
from router.keyword_router import KeywordRouter
from router.modules.base_module import OmniaContext
from router.modules.omnia_studio import OmniaStudioModule


@pytest.fixture
def ctx():
    return OmniaContext("u", 0.1, "s", age_band="minor")


class TestColor:
    @pytest.mark.parametrize("text,expected", [
        ("paleta para #ff5500", "#FF5500"), ("color #0af", "#00AAFF"), ("#00C8FF", "#00C8FF"),
        ("sin color", None), ("#12345", None), ("#GGGGGG", None), ("", None), (None, None)])
    def test_parse_hex(self, text, expected):
        assert st.parse_hex(text) == expected

    def test_contrast_reference_values(self):
        assert st.contrast_ratio("#000000", "#FFFFFF") == 21.0
        assert st.contrast_ratio("#FFFFFF", "#FFFFFF") == 1.0
        assert st.contrast_ratio("#FFFFFF", "#000000") == 21.0           # simétrico
        # valor conocido de WCAG: #777777 sobre blanco ≈ 4.48 (no llega a AA)
        assert st.contrast_ratio("#777777", "#FFFFFF") == 4.48

    @pytest.mark.parametrize("bad", ["", "red", "#12", "#1234567", None, 5, "#GGGGGG"])
    def test_invalid_color_raises(self, bad):
        with pytest.raises(st.InvalidColor):
            st.contrast_ratio(bad, "#000000")

    def test_rotate_180_and_360(self):
        assert st.rotate("#FF0000", 180) == "#00FFFF"
        assert st.rotate("#00C8FF", 360) == "#00C8FF"
        assert st.rotate("#808080", 90) == "#808080"                        # gris: sin matiz

    def test_best_text_picks_higher_contrast(self):
        assert st.best_text("#000000")["text"] == "#FFFFFF"
        assert st.best_text("#FFFFFF")["text"] == "#000000"
        t = st.best_text("#00C8FF")
        assert t["text"] == "#000000" and t["aa"] is True

    def test_palette_shape_and_values(self):
        p = st.build_palette()
        assert p["base"] == "#00C8FF" and p["background"] == "#000000" and len(p["colors"]) == 6
        assert p["colors"][1]["role"] == "complementario" and p["colors"][1]["hex"] == "#FF3700"
        for c in p["colors"]:
            assert c["on_black"] == st.contrast_ratio(c["hex"], "#000000")
            assert c["best_text"]["ratio"] >= 4.5 or c["best_text"]["aa"] is False

    def test_palette_lowercase_base_normalized(self):
        assert st.build_palette("#ff5500")["base"] == "#FF5500"

    def test_palette_invalid_base(self):
        with pytest.raises(st.InvalidColor):
            st.build_palette("naranja")


class TestLightingAndPrompt:
    @pytest.mark.parametrize("text,name", [
        ("iluminación tech noir", "Tech-noir"), ("estilo Rembrandt", "Rembrandt"), ("luz mariposa", "Mariposa (butterfly)"),
        ("foto a contraluz", "Contraluz (rim)"), ("high key", "High-key"), ("fondo negro", "Low-key")])
    def test_find_scheme(self, text, name):
        assert st.find_scheme(text)["name"] == name

    def test_find_scheme_none(self):
        assert st.find_scheme("hola") is None and st.find_scheme("") is None and st.find_scheme(None) is None

    def test_describe_scheme_has_all_parts(self):
        d = st.describe_scheme(st.find_scheme("tech noir"))
        for word in ("Luz principal", "Relleno", "Contraluz", "Relación de luces", "Consejo"):
            assert word in d

    @pytest.mark.parametrize("msg,subject", [
        ("prompt para imagen de un astronauta en una ciudad lluviosa", "un astronauta en una ciudad lluviosa"),
        ("dame un prompt de un faro en una tormenta", "un faro en una tormenta"),
        ("prompt creativo sobre un dragón de cristal.", "un dragón de cristal"),
        ("necesito un prompt creativo para fotografía", None), ("prompt", None), ("", None), (None, None),
        ("prompt para imagen de ab", None),
        ("prompt para imagen de un faro con iluminación tech-noir y colores #00c8ff", "un faro"),
        ("prompt de un faro, estilo retro", "un faro"), ("prompt de un faro #00C8FF", "un faro"),
        ("prompt de iluminación tech noir", None)])
    def test_extract_subject(self, msg, subject):
        assert st.extract_subject(msg) == subject

    def test_subject_is_capped(self):
        assert len(st.extract_subject("prompt de " + "x" * 1000)) == st.MAX_SUBJECT

    def test_build_prompt_contains_parts_and_cleans_whitespace(self):
        out = st.build_prompt("un  faro\n en la tormenta", st.find_scheme("rembrandt"), ["#00C8FF"], "estilo retro")
        assert "un faro en la tormenta" in out and "rembrandt" in out and "#00C8FF" in out and "retro" in out
        assert "\n" not in out

    def test_build_prompt_requires_subject(self):
        with pytest.raises(ValueError):
            st.build_prompt("  ")

    @pytest.mark.parametrize("text,blocked", [("desnudo artístico", True), ("contenido sexual", True), ("un NSFW", True),
                                              ("un faro", False), ("", False), (None, False)])
    def test_is_blocked(self, text, blocked):
        assert st.is_blocked(text) is blocked


class TestModule:
    m = OmniaStudioModule()

    def test_menu_when_nothing_specific(self, ctx):
        r = self.m.handle("necesito ayuda visual", ctx)
        assert r.data["status"] == "menu" and "Tech-noir" in r.text

    def test_palette_default_and_custom(self, ctx):
        d = self.m.handle("dame una paleta de colores", ctx)
        assert d.data["status"] == "palette" and d.data["palette"]["base"] == "#00C8FF"
        c = self.m.handle("paleta para #FF5500", ctx)
        assert c.data["palette"]["base"] == "#FF5500" and "WCAG" in c.text

    def test_lighting_detail_and_list(self, ctx):
        d = self.m.handle("explícame la iluminación tech noir", ctx)
        assert d.data["status"] == "lighting" and "cian" in d.text
        l = self.m.handle("quiero un esquema de iluminación", ctx)
        assert l.data["status"] == "lighting_list" and l.requires_followup is True

    def test_prompt_with_scheme_and_colors(self, ctx):
        r = self.m.handle("prompt para imagen de un astronauta en una ciudad lluviosa con iluminación tech-noir y colores #00c8ff #000", ctx)
        assert r.data["status"] == "prompt" and r.data["scheme"] == "Tech-noir"
        assert "#00C8FF" in r.data["prompt"] and "#000000" in r.data["prompt"] and "personas reales" in r.text

    def test_prompt_needs_subject(self, ctx):
        r = self.m.handle("necesito un prompt creativo para fotografía", ctx)
        assert r.data["status"] == "needs_subject" and r.requires_followup is True

    @pytest.mark.parametrize("msg", ["prompt para imagen de una escena sexual", "paleta para contenido nsfw",
                                     "iluminación para fotos desnudo"])
    def test_explicit_requests_are_blocked_in_every_intent(self, ctx, msg):
        assert self.m.handle(msg, ctx).data["status"] == "blocked"

    def test_hex_garbage_is_ignored(self, ctx):
        r = self.m.handle("prompt de un faro #zzz #12345 colores #00c8ff", ctx)
        assert r.data["status"] == "prompt" and "#00C8FF" in r.data["prompt"] and "zzz" not in r.data["prompt"]

    def test_no_user_data_is_stored(self, ctx):
        ctx.data_store = None            # el módulo funciona sin almacén
        assert self.m.handle("paleta", ctx).data["status"] == "palette"


class TestRouting:
    @pytest.mark.parametrize("msg", ["necesito un prompt creativo para fotografía", "dame una paleta para mi marca",
                                     "explícame la iluminación tech noir", "iluminación rembrandt"])
    def test_routes_to_studio(self, msg):
        r = KeywordRouter().route(msg, OmniaContext("u", 0.1, "s", age_band="minor"))
        assert r.module_response.module_name == "OmniaStudio"
