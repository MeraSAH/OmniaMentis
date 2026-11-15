# tests/unit/test_nutrition.py
"""
* UBICACIÓN: OmniaMentis/tests/unit/test_nutrition.py
* PROPÓSITO: Tests del motor de NutriVida (src/core/health/nutrition.py) y del
*            módulo NutriVida (src/router/modules/nutrivida.py).
* CREADO: 2026-10-18
* ESTADO: Test Permanente
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from core.health import nutrition as nut
from router.modules.base_module import OmniaContext
from router.modules.nutrivida import NutriVidaModule


class FakeStore:
    def __init__(self, fail=False):
        self.rows, self.fail = [], fail

    def add(self, account_id, module, kind, payload):
        if self.fail:
            raise RuntimeError("disco lleno")
        self.rows.append((account_id, module, kind, payload))
        return len(self.rows)


def ctx(band="adult", store=None):
    return OmniaContext(user_id="acc-1", consciousness_level=0.1, session_id="s",
                        age_band=band, data_store=store)


class TestBmi:
    @pytest.mark.parametrize("w,h,expected", [(70, 175, 22.9), (50, 170, 17.3), (100, 180, 30.9), (60, 150, 26.7)])
    def test_values(self, w, h, expected):
        assert nut.compute_bmi(w, h) == expected

    @pytest.mark.parametrize("w,h", [(0, 170), (-5, 170), (19.9, 170), (301, 170), (70, 99), (70, 251),
                                     ("70", 170), (None, 170), (True, 170), (float("nan"), 170), (float("inf"), 170)])
    def test_invalid(self, w, h):
        with pytest.raises(nut.InvalidMeasure):
            nut.compute_bmi(w, h)

    @pytest.mark.parametrize("bmi,cat", [(18.4, "bajo peso"), (18.5, "saludable"), (24.9, "saludable"),
                                         (25.0, "sobrepeso"), (29.9, "sobrepeso"), (30.0, "obesidad")])
    def test_adult_categories(self, bmi, cat):
        assert nut.bmi_category(bmi, "adult") == cat

    @pytest.mark.parametrize("band", ["minor", "minor_basic", "", None, "otro"])
    def test_non_adults_are_never_classified(self, band):
        assert nut.bmi_category(22.0, band) is None
        assert nut.bmi_category(40.0, band) is None


class TestWater:
    def test_adult_scales_with_weight(self):
        assert nut.water_glasses(70, "adult") == 10   # 2450 ml / 250
        assert nut.water_glasses(20, "adult") == 6    # piso
        assert nut.water_glasses(300, "adult") == 16  # techo

    @pytest.mark.parametrize("band", ["minor", "minor_basic", ""])
    def test_non_adults_fixed_eight(self, band):
        assert nut.water_glasses(95, band) == 8


class TestCalories:
    def test_man_moderate(self):
        # BMR = 88.362 + 1071.76 + 863.82 - 170.31 = 1853.632 ; x 1.55 = 2873.2
        assert nut.daily_calories(80, 180, 30, "hombre", "moderado", "adult") == 2873

    def test_woman_sedentary(self):
        # BMR = 447.593 + 554.82 + 511.17 - 173.2 = 1340.383 ; x 1.2 = 1608.46
        assert nut.daily_calories(60, 165, 40, "mujer", "sedentario", "adult") == 1608

    @pytest.mark.parametrize("band", ["minor", "minor_basic", "", None])
    def test_never_for_minors_or_unknown(self, band):
        with pytest.raises(nut.NotApplicable):
            nut.daily_calories(60, 165, 16, "mujer", "moderado", band)

    @pytest.mark.parametrize("kwargs", [
        dict(sex="otro", activity="moderado", age=30),
        dict(sex="hombre", activity="extremo", age=30),
        dict(sex="hombre", activity="moderado", age=17),
        dict(sex="hombre", activity="moderado", age=200),
    ])
    def test_invalid_inputs(self, kwargs):
        with pytest.raises(nut.InvalidMeasure):
            nut.daily_calories(70, 175, kwargs["age"], kwargs["sex"], kwargs["activity"], "adult")


class TestExtract:
    def test_cm_and_kg(self):
        assert nut.extract_measures("peso 70 kg y mido 175 cm") == {"weight_kg": 70.0, "height_cm": 175.0}

    def test_meters_with_comma(self):
        m = nut.extract_measures("peso 68,5 kilos y mido 1,72 m")
        assert m["weight_kg"] == 68.5 and m["height_cm"] == 172.0

    def test_mido_word_in_meters(self):
        assert nut.extract_measures("mido 1.80")["height_cm"] == 180.0

    def test_age_sex_activity(self):
        m = nut.extract_measures("soy hombre, tengo 30 años, 80 kg, 180 cm, actividad moderada")
        assert m == {"weight_kg": 80.0, "height_cm": 180.0, "age": 30, "sex": "hombre", "activity": "moderado"}

    def test_ambiguous_sex_is_ignored(self):
        assert "sex" not in nut.extract_measures("un hombre y una mujer")

    def test_age_is_not_taken_as_weight_or_height(self):
        m = nut.extract_measures("tengo 25 años")
        assert m == {"age": 25}

    @pytest.mark.parametrize("text", ["", None, "hola", "¿Cuántas calorías tiene una manzana?", "😀" * 50])
    def test_nothing_found_never_raises(self, text):
        assert nut.extract_measures(text) == {}

    def test_huge_input_is_fast_and_safe(self):
        nut.extract_measures("9" * 100000)
        nut.extract_measures("peso " + "1" * 50000)

    def test_weight_loss_detection(self):
        assert nut.wants_weight_loss("quiero bajar de peso")
        assert nut.wants_weight_loss("un déficit calórico")
        assert not nut.wants_weight_loss("quiero subir masa")


class TestModule:
    m = NutriVidaModule()

    def test_asks_for_measures_when_missing(self):
        r = self.m.handle("calcula mi imc", ctx())
        assert r.requires_followup and r.data["status"] == "needs_measures"
        assert "base de alimentos" in r.text

    def test_food_question_is_honest(self):
        r = self.m.handle("¿Cuántas calorías tiene una manzana?", ctx())
        assert r.data["status"] == "needs_measures"
        assert "no puedo darte las calorías de una comida" in r.text

    def test_adult_full_calculation_and_save(self):
        store = FakeStore()
        r = self.m.handle("soy hombre, 30 años, peso 80 kg, mido 180 cm, actividad moderada", ctx(store=store))
        assert r.data["bmi"] == 24.7 and r.data["bmi_category"] == "saludable"
        assert r.data["daily_calories"] == 2873
        assert r.data["water_glasses"] == 12
        assert r.data["saved"] is True and not r.requires_followup
        assert store.rows == [("acc-1", "NutriVida", "calculo", {
            "bmi": 24.7, "bmi_category": "saludable", "water_glasses": 12, "weight_kg": 80.0,
            "height_cm": 180.0, "daily_calories": 2873})]
        assert "no es" in r.text.lower() or "no un diagnóstico" in r.text

    def test_adult_missing_extra_data_asks_followup(self):
        r = self.m.handle("peso 70 kg y mido 175 cm", ctx())
        assert r.requires_followup is True
        assert "daily_calories" not in r.data
        assert "tu edad" in r.text

    def test_underweight_and_obesity_suggest_professional(self):
        assert "profesional" in self.m.handle("peso 45 kg mido 175 cm", ctx()).text
        assert "profesional" in self.m.handle("peso 120 kg mido 170 cm", ctx()).text

    @pytest.mark.parametrize("band", ["minor", "minor_basic"])
    def test_minor_gets_number_but_no_class_no_calories(self, band):
        store = FakeStore()
        r = self.m.handle("peso 55 kg, mido 165 cm, tengo 16 años, mujer, activa moderada", ctx(band, store))
        assert r.data["bmi"] == 20.2
        assert r.data["bmi_category"] is None
        assert "daily_calories" not in r.data
        assert r.data["water_glasses"] == 8
        assert "pediatra" in r.text
        assert "kcal" not in r.text
        assert not r.requires_followup

    @pytest.mark.parametrize("band", ["minor", "minor_basic", ""])
    def test_minor_weight_loss_is_redirected_not_calculated(self, band):
        store = FakeStore()
        r = self.m.handle("quiero bajar de peso, peso 60 kg y mido 165 cm", ctx(band, store))
        assert r.data["status"] == "minor_safe_redirect"
        assert store.rows == []
        assert "pediatra" in r.text and "kcal" not in r.text

    def test_adult_weight_loss_request_still_gets_numbers_not_a_diet(self):
        r = self.m.handle("quiero bajar de peso, peso 90 kg y mido 170 cm", ctx())
        assert r.data["status"] == "calculated"
        assert "dieta" not in r.text.lower()

    def test_invalid_measures_not_saved(self):
        store = FakeStore()
        r = self.m.handle("peso 500 kg y mido 175 cm", ctx(store=store))
        assert r.data["status"] == "invalid_measures" and store.rows == []

    def test_storage_failure_does_not_break_the_answer(self):
        r = self.m.handle("peso 70 kg y mido 175 cm", ctx(store=FakeStore(fail=True)))
        assert r.data["bmi"] == 22.9 and r.data["saved"] is False

    def test_works_without_store(self):
        r = self.m.handle("peso 70 kg y mido 175 cm", ctx())
        assert r.data["saved"] is False

    def test_unknown_band_is_treated_as_minor(self):
        r = self.m.handle("peso 70 kg y mido 175 cm", ctx(""))
        assert r.data["bmi_category"] is None and "daily_calories" not in r.data
