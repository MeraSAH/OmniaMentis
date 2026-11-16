"""Pruebas de router/slash.py (comandos «/» del desarrollador)."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from router import slash

MODS = ["NutriVida", "Corporal Verified", "OmniaCore"]


class TestParse:
    @pytest.mark.parametrize("msg", ["hola", "", "  hola /x", "a/[b] c", None, 5])
    def test_not_a_command(self, msg):
        assert slash.parse(msg) is None

    @pytest.mark.parametrize("msg", ["/", "  /  ", "/ayuda", "/[sin cierre", "/[] algo", "/Corporal Verified 15"])
    def test_bad_format_shows_list(self, msg):
        assert slash.parse(msg).kind == "list"

    def test_module_command(self):
        c = slash.parse("/[Corporal Verified] hueso púbico 15.2")
        assert (c.kind, c.module, c.text) == ("module", "Corporal Verified", "hueso púbico 15.2")

    def test_spaces_and_multiline(self):
        c = slash.parse("  /[ NutriVida ]   soy hombre,\npeso 70  ")
        assert c.module == "NutriVida" and c.text == "soy hombre,\npeso 70"

    def test_command_without_text(self):
        assert slash.parse("/[OmniaCore]").text == ""

    def test_name_too_long_is_not_a_module(self):
        assert slash.parse("/[" + "a" * 61 + "] x").kind == "list"


class TestResolve:
    def test_case_and_spaces_insensitive(self):
        assert slash.resolve_module("corporal   verified", MODS) == "Corporal Verified"
        assert slash.resolve_module("NUTRIVIDA", MODS) == "NutriVida"

    def test_unknown(self):
        assert slash.resolve_module("Nada", MODS) is None
        assert slash.resolve_module("", MODS) is None


def test_help_lists_every_module_and_the_format():
    h = slash.help_text(MODS)
    assert all(f"/[{m}]" in h for m in MODS) and "hueso púbico" in h
