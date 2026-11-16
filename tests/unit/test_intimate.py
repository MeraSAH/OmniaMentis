"""Pruebas de core/health/intimate.py (medida íntima opcional; solo adultos verificados)."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from core.health import intimate
from core.health.nutrition import InvalidMeasure


class TestParse:
    @pytest.mark.parametrize("msg,expected", [
        ("hueso púbico 15.2", ("hueso_pubico", 15.2)),
        ("hueso pubico 15,2 cm", ("hueso_pubico", 15.2)),
        ("BPEL 16", ("hueso_pubico", 16.0)),
        ("base 14.5", ("base", 14.5)),
        ("desde la base 14", ("base", 14.0)),
        ("perímetro 12 cm", ("perimetro", 12.0)),
        ("circunferencia del miembro 11,5", ("perimetro", 11.5)),
        ("medida íntima: hueso púbico, 15.2 centímetros", ("hueso_pubico", 15.2)),
    ])
    def test_ok(self, msg, expected):
        assert intimate.parse_message(msg) == expected

    def test_missing_pieces(self):
        assert intimate.parse_message("hueso púbico") == ("hueso_pubico", None)
        assert intimate.parse_message("15.2") == (None, 15.2)
        assert intimate.parse_message("") == (None, None)
        assert intimate.parse_message(None) == (None, None)

    @pytest.mark.parametrize("msg", ["cintura 85 base", "mi peso 70 kg", "perímetro del brazo 32",
                                     "cuello 38", "porcentaje de grasa 20 base"])
    def test_other_body_measures_are_not_intimate(self, msg):
        assert intimate.parse_message(msg) == (None, None)
        assert intimate.looks_intimate(msg) is False

    def test_looks_intimate(self):
        assert intimate.looks_intimate("hueso púbico 15.2")
        assert intimate.looks_intimate("hueso púbico")
        assert not intimate.looks_intimate("base")
        assert intimate.looks_intimate("quiero registrar mi medida íntima")
        assert not intimate.looks_intimate("¿Cómo mido mi porcentaje de grasa corporal?")
        assert not intimate.looks_intimate("hola")
        assert not intimate.looks_intimate("")

    def test_year_or_big_numbers_not_taken_as_cm(self):
        assert intimate.parse_message("base 2026")[1] is None
        assert intimate.parse_message("base 123")[1] is None


class TestBuildPayload:
    def test_ok(self):
        assert intimate.build_payload("hueso_pubico", 15.24) == {"origen": "hueso_pubico", "tipo": "longitud", "cm": 15.2}
        assert intimate.build_payload("perimetro", 12) == {"origen": "perimetro", "tipo": "perimetro", "cm": 12.0}

    @pytest.mark.parametrize("origin", ["", None, "otra", 5])
    def test_bad_origin(self, origin):
        with pytest.raises(InvalidMeasure):
            intimate.build_payload(origin, 15)

    @pytest.mark.parametrize("cm", [None, "15", True, float("nan"), float("inf"), -1, 0, 2.9, 30.1, 100])
    def test_bad_cm_longitud(self, cm):
        with pytest.raises(InvalidMeasure):
            intimate.build_payload("base", cm)

    @pytest.mark.parametrize("cm", [4.9, 25.1])
    def test_bad_cm_perimetro(self, cm):
        with pytest.raises(InvalidMeasure):
            intimate.build_payload("perimetro", cm)

    def test_edges(self):
        intimate.build_payload("base", 3.0)
        intimate.build_payload("base", 30.0)
        intimate.build_payload("perimetro", 5.0)
        intimate.build_payload("perimetro", 25.0)
