# tests/unit/test_body.py
"""
* UBICACIÓN: OmniaMentis/tests/unit/test_body.py
* PROPÓSITO: Tests de composición corporal (src/core/health/body.py) y de su uso en NutriVida.
*            Los valores esperados están calculados a mano (ver comentarios), no con el mismo código.
* CREADO: 2026-11-15
* ESTADO: Test Permanente
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from core.health import body
from core.health.nutrition import InvalidMeasure
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
    return OmniaContext(user_id="acc-1", consciousness_level=0.1, session_id="s", age_band=band, data_store=store)


class TestNavyBodyFat:
    def test_man_by_hand(self):
        # cintura−cuello = 47; log10(47)=1.67210; log10(175)=2.24304
        # denom = 1.0324 − 0.19077·1.67210 + 0.15456·2.24304 = 1.06008 ; 495/1.06008 − 450 = 16.9
        assert body.navy_body_fat("hombre", 175, 38, 85) == 16.9

    def test_woman_by_hand(self):
        # 70+98−32 = 136; log10(136)=2.13354; log10(165)=2.21748
        # denom = 1.29579 − 0.35004·2.13354 + 0.221·2.21748 = 1.03902 ; 495/1.03902 − 450 = 26.4
        assert body.navy_body_fat("mujer", 165, 32, 70, 98) == 26.4

    def test_bigger_waist_means_more_fat(self):
        assert body.navy_body_fat("hombre", 175, 38, 95) > body.navy_body_fat("hombre", 175, 38, 85)

    def test_woman_needs_hip(self):
        with pytest.raises(InvalidMeasure, match="cadera"):
            body.navy_body_fat("mujer", 165, 32, 70)

    def test_man_ignores_hip(self):
        assert body.navy_body_fat("hombre", 175, 38, 85, 999) == 16.9   # la cadera no entra en la fórmula de hombres
        assert body.navy_body_fat("hombre", 175, 38, 85, None) == 16.9

    @pytest.mark.parametrize("sex", [None, "", "otro", 1])
    def test_sex_is_required(self, sex):
        with pytest.raises(InvalidMeasure):
            body.navy_body_fat(sex, 175, 38, 85)

    def test_waist_not_bigger_than_neck(self):
        with pytest.raises(InvalidMeasure, match="mayor que el cuello"):
            body.navy_body_fat("hombre", 175, 40, 40)
        with pytest.raises(InvalidMeasure):
            body.navy_body_fat("hombre", 175, 50, 45)

    @pytest.mark.parametrize("args", [(175, 10, 85), (175, 38, 300), (50, 38, 85), (175, "38", 85), (175, True, 85),
                                      (175, float("nan"), 85), (175, 38, float("inf"))])
    def test_out_of_range_or_wrong_types(self, args):
        with pytest.raises(InvalidMeasure):
            body.navy_body_fat("hombre", *args)

    def test_unbelievable_result_is_rejected(self):
        with pytest.raises(InvalidMeasure, match="no es creíble"):
            body.navy_body_fat("hombre", 175, 36, 40)        # cintura−cuello = 4 → grasa negativa


class TestFatCategory:
    @pytest.mark.parametrize("sex,pct,name", [
        ("hombre", 5, "grasa esencial"), ("hombre", 6, "atlético"), ("hombre", 13.9, "atlético"),
        ("hombre", 14, "en forma"), ("hombre", 17.9, "en forma"), ("hombre", 18, "aceptable"),
        ("hombre", 24.9, "aceptable"), ("hombre", 25, "obesidad"), ("hombre", 40, "obesidad"),
        ("mujer", 13, "grasa esencial"), ("mujer", 14, "atlético"), ("mujer", 21, "en forma"),
        ("mujer", 25, "aceptable"), ("mujer", 31.9, "aceptable"), ("mujer", 32, "obesidad"),
    ])
    def test_bands(self, sex, pct, name):
        assert body.fat_category(sex, pct) == name


class TestSomatotype:
    def test_ponderal_index_by_hand(self):
        # cbrt(70)=4.1213 ; 175/4.1213 = 42.46
        assert round(body.ponderal_index(175, 70), 2) == 42.46

    def test_ectomorphy_three_branches(self):
        assert body.ectomorphy(175, 70) == 2.5           # IP 42.46 ≥ 40.75: 0.732·42.46 − 28.58
        # IP 39.5 → 0.463·39.5 − 17.63 = 0.66 ; peso 64.17 kg con 175 cm da IP≈39.5
        assert body.ectomorphy(175, 86.0) == pytest.approx(0.1, abs=0.6)
        assert body.ectomorphy(160, 110) == 0.1          # IP bajo (≤ 38.25)

    def test_ectomorphy_middle_branch(self):
        # 170 cm y 80 kg: cbrt(80)=4.3089 ; IP = 39.45 → 0.463·39.45 − 17.63 = 0.64
        assert body.ectomorphy(170, 80) == 0.6

    def test_heath_carter_by_hand(self):
        # X = (10+12+8)·170.18/175 = 29.174 → endo = −0.7182 + 4.2331 − 0.5787 + 0.0348 = 2.97 → 3.0
        # meso = 6.006 + 5.890 + 0.188·(32−1.0) + 0.161·(36−0.7) − 0.131·175 + 4.5 = 4.98 → 5.0
        assert body.heath_carter(175, 70, 10, 12, 8, 7, 32, 36, 7, 9.8) == (3.0, 5.0, 2.5)

    @pytest.mark.parametrize("idx,val", [(2, 1), (4, 200), (6, 80), (8, 2), (9, 40)])
    def test_heath_carter_validates(self, idx, val):
        args = [175, 70, 10, 12, 8, 7, 32, 36, 7, 9.8]
        args[idx] = val
        with pytest.raises(InvalidMeasure):
            body.heath_carter(*args)

    def test_estimates_by_hand(self):
        # endo: 16.9/4.5 = 3.76 → 3.8
        assert body.estimate_endomorphy(16.9) == 3.8
        assert body.estimate_endomorphy(2.0) == 1.0       # mínimo 1.0
        assert body.estimate_endomorphy(60.0) == 12.0     # máximo 12.0
        # meso: magro = 70·0.831 = 58.17 ; FFMI = 58.17/3.0625 = 18.99 ; 0.6·18.99 − 7.4 = 3.99 ;
        # relación = ((32+36)/2)/175 = 0.1943 → ajuste −0.057 → 3.94 → 3.9
        assert body.estimate_mesomorphy(70, 175, 16.9, 32, 36) == 3.9

    def test_meso_is_bounded(self):
        assert 0.5 <= body.estimate_mesomorphy(250, 150, 5, 70, 70) <= 9.0
        assert body.estimate_mesomorphy(25, 200, 55, 15, 15) >= 0.5

    def test_stronger_limbs_raise_meso(self):
        assert body.estimate_mesomorphy(70, 175, 16.9, 40, 42) > body.estimate_mesomorphy(70, 175, 16.9, 28, 32)

    def test_full_estimate(self):
        r = body.estimate_somatotype("hombre", 70, 175, 38, 85, None, 32, 36)
        assert (r["body_fat"], r["endo"], r["meso"], r["ecto"]) == (16.9, 3.8, 3.9, 2.5)
        assert r["fat_category"] == "en forma" and r["somatotype"] == "mesomorfo-endomorfo (mixto)"
        # X = ecto − endo = −1.3 ; Y = 2·meso − (endo + ecto) = 7.8 − 6.3 = 1.5
        assert (r["chart_x"], r["chart_y"]) == (-1.3, 1.5)

    @pytest.mark.parametrize("e,m,c,name", [
        (6, 3, 1, "endomorfo"), (2, 6, 2, "mesomorfo"), (1.5, 2, 6, "ectomorfo"),
        (4, 4.2, 1, "mesomorfo-endomorfo (mixto)"), (3, 3.2, 3.4, "central (equilibrado)"),
        (1, 5, 5.2, "ectomorfo-mesomorfo (mixto)"),
    ])
    def test_classify(self, e, m, c, name):
        assert body.classify(e, m, c) == name

    def test_somatochart_coordinates(self):
        assert body.somatochart(2, 5, 3) == {"chart_x": 1.0, "chart_y": 5.0}


class TestExtraction:
    def test_all_parts(self):
        got = body.extract_girths("cuello 38, cintura 85 cm, cadera: 100, brazo 32 y pantorrilla de 36,5")
        assert got == {"neck_cm": 38.0, "waist_cm": 85.0, "hip_cm": 100.0, "arm_cm": 32.0, "calf_cm": 36.5}

    def test_partial_and_empty(self):
        assert body.extract_girths("mi cintura es 90") == {"waist_cm": 90.0}
        assert body.extract_girths("") == {} and body.extract_girths(None) == {}

    def test_does_not_cross_lines_or_words(self):
        assert body.extract_girths("cuello\n85") == {}
        assert body.extract_girths("cintura") == {}

    @pytest.mark.parametrize("text,expected", [
        ("calcula mi somatotipo", True), ("mi porcentaje de grasa", True), ("tengo cintura 85", True),
        ("cuello 38", True), ("quiero comer sano", False), ("peso 70 kg y mido 175 cm", False), ("", False),
    ])
    def test_wants(self, text, expected):
        assert body.wants_body_composition(text) is expected


FULL = "soy hombre, peso 70 kg, mido 175 cm, cuello 38, cintura 85, brazo 32, pantorrilla 36"


class TestNutriVidaBody:
    def test_full_adult_flow_saves_composition(self):
        store = FakeStore()
        r = NutriVidaModule().handle(FULL, ctx(store=store))
        assert r.data["status"] == "body_composition" and r.data["saved"] is True
        assert "16.9 %" in r.text and "mesomorfo-endomorfo" in r.text and "estimaciones de OmniaMentis" in r.text
        assert "no un diagnóstico" in r.text and "margen de error" in r.text
        assert len(store.rows) == 1 and store.rows[0][1:3] == ("NutriVida", "composicion")
        p = store.rows[0][3]
        assert p["body_fat"] == 16.9 and p["endo"] == 3.8 and p["meso"] == 3.9 and p["ecto"] == 2.5 and p["bmi"] == 22.9
        assert "saved" not in p and p["sex"] == "hombre"

    def test_without_arm_and_calf_gives_fat_and_asks_for_them(self):
        r = NutriVidaModule().handle("soy hombre, peso 70 kg, mido 175 cm, cuello 38, cintura 85", ctx(store=FakeStore()))
        assert r.data["status"] == "body_composition" and r.requires_followup is True
        assert "16.9 %" in r.text and "brazo y pantorrilla" in r.text and "Somatotipo estimado" not in r.text

    def test_woman_needs_hip(self):
        r = NutriVidaModule().handle("soy mujer, peso 60 kg, mido 165 cm, cuello 32, cintura 70", ctx())
        assert r.data["status"] == "needs_measures" and "cadera" in r.text

    def test_woman_full(self):
        r = NutriVidaModule().handle("soy mujer, peso 60 kg, mido 165 cm, cuello 32, cintura 70, cadera 98", ctx())
        assert r.data["status"] == "body_composition" and "26.4 %" in r.text and "aceptable" in r.text

    def test_missing_things_are_listed(self):
        r = NutriVidaModule().handle("mi cintura es 85", ctx())
        assert r.data["status"] == "needs_measures" and r.requires_followup is True
        for word in ("hombre o mujer", "peso", "altura", "cuello"):
            assert word in r.text

    def test_invalid_measures_do_not_save(self):
        store = FakeStore()
        r = NutriVidaModule().handle("soy hombre, peso 70 kg, mido 175 cm, cuello 40, cintura 40", ctx(store=store))
        assert r.data["status"] == "invalid_measures" and store.rows == []

    def test_store_failure_still_answers(self):
        r = NutriVidaModule().handle(FULL, ctx(store=FakeStore(fail=True)))
        assert r.data["status"] == "body_composition" and r.data["saved"] is False and "16.9 %" in r.text

    def test_no_store_still_answers(self):
        r = NutriVidaModule().handle(FULL, ctx(store=None))
        assert r.data["saved"] is False

    @pytest.mark.parametrize("band", ["minor", "minor_basic", ""])
    def test_minors_and_unknown_get_nothing_computed(self, band):
        store = FakeStore()
        r = NutriVidaModule().handle(FULL, ctx(band, store))
        assert r.data["status"] == "minor_not_applicable" and store.rows == []
        assert "%" not in r.text.replace("100 %", "") and "somatotipo estimado" not in r.text.lower()
        assert "bajar de peso" not in r.text.lower()

    def test_normal_bmi_flow_is_unchanged(self):
        r = NutriVidaModule().handle("peso 70 kg y mido 175 cm", ctx(store=FakeStore()))
        assert r.data["status"] in ("calculated",) and r.data["bmi"] == 22.9

    def test_keywords_do_not_steal_corporal_phrases(self):
        from router.modules.corporal_verified import CorporalVerifiedModule
        n, c = NutriVidaModule(), CorporalVerifiedModule()
        for msg in ("¿Cómo mido mi porcentaje de grasa corporal?", "cual es mi porcentaje de grasa",
                    "mi cintura mide 85"):
            assert n.confidence(msg) < c.confidence(msg)

    def test_measures_and_somatotype_route_to_nutrivida(self):
        from router.modules.corporal_verified import CorporalVerifiedModule
        n, c = NutriVidaModule(), CorporalVerifiedModule()
        for msg in ("soy hombre, peso 70 kg, mido 175 cm, cuello 38, cintura 85, brazo 32, pantorrilla 36",
                    "quiero saber mi somatotipo"):
            assert n.confidence(msg) > c.confidence(msg)
