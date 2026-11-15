# tests/unit/test_router_policy.py
"""
* UBICACIÓN: OmniaMentis/tests/unit/test_router_policy.py
* PROPÓSITO: Tests de la política de acceso por edad de los módulos
*            (src/router/policy.py) y de su aplicación en el router y en
*            route_or_none. Los módulos no deciden: decide el motor.
* CREADO: 2026-10-17
* ESTADO: Test Permanente
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from router import policy
from router.integration import route_or_none, set_auth_checker
from router.keyword_router import MODULE_REGISTRY, KeywordRouter
from router.modules.base_module import OmniaContext, OmniaModule, ModuleResponse

NUTRI = "¿Cuántas calorías tiene una manzana?"
GYM = "Quiero armar una rutina de gimnasio"
CORPORAL = "¿Cómo mido mi porcentaje de grasa corporal?"
CODE = "ejecutar codigo python de prueba"
FUNNEL = "quiero crear un embudo de venta automatizado"


def ctx(band):
    return OmniaContext(user_id="u", consciousness_level=0.1, session_id="s", age_band=band)


class TestPolicyTable:
    def test_every_registered_module_has_a_rule(self):
        names = {cls().name for cls in MODULE_REGISTRY}
        assert names == set(policy.MODULE_MIN_AGE_BAND)

    def test_all_rules_use_known_bands(self):
        assert set(policy.MODULE_MIN_AGE_BAND.values()) <= set(policy.AGE_BANDS)

    def test_bands_are_ordered(self):
        assert policy.AGE_BANDS == ("minor", "minor_basic", "adult")

    @pytest.mark.parametrize("user,minimum,expected", [
        ("minor", "minor", True), ("minor", "minor_basic", False), ("minor", "adult", False),
        ("minor_basic", "minor", True), ("minor_basic", "minor_basic", True), ("minor_basic", "adult", False),
        ("adult", "minor", True), ("adult", "minor_basic", True), ("adult", "adult", True),
    ])
    def test_band_allows(self, user, minimum, expected):
        assert policy.band_allows(user, minimum) is expected

    @pytest.mark.parametrize("bad", ["", None, "ADULT", "child", 18, [], "under_13", "adult "])
    def test_unknown_band_is_denied_everywhere(self, bad):
        for minimum in policy.AGE_BANDS:
            assert policy.band_allows(bad, minimum) is False
        for name in policy.MODULE_MIN_AGE_BAND:
            assert policy.module_allowed(name, bad) is False

    def test_module_without_rule_is_denied_even_for_adults(self):
        assert policy.module_allowed("ModuloNuevo", "adult") is False

    def test_corporal_forge_engine_are_adult_only(self):
        for name in ("Corporal Verified", "OmniaForge", "OmniaEngine"):
            assert policy.module_allowed(name, "adult") is True
            assert policy.module_allowed(name, "minor_basic") is False
            assert policy.module_allowed(name, "minor") is False

    def test_athletics_not_for_13_14(self):
        assert policy.module_allowed("OmniaAthletics", "minor") is False
        assert policy.module_allowed("OmniaAthletics", "minor_basic") is True


class TestRouterAppliesPolicy:
    def test_adult_routes_as_before(self):
        r = KeywordRouter().route(NUTRI, ctx("adult"))
        assert r.should_route and r.module_response.module_name == "NutriVida"
        assert r.age_restricted_module is None

    def test_minor_can_use_nutrivida(self):
        r = KeywordRouter().route(NUTRI, ctx("minor"))
        assert r.should_route is True

    def test_minor_blocked_from_athletics(self):
        r = KeywordRouter().route(GYM, ctx("minor"))
        assert r.should_route is False
        assert r.module_response is None
        assert r.age_restricted_module == "OmniaAthletics"

    def test_minor_basic_allowed_athletics(self):
        assert KeywordRouter().route(GYM, ctx("minor_basic")).should_route is True

    @pytest.mark.parametrize("band", ["minor", "minor_basic"])
    @pytest.mark.parametrize("msg,mod", [(CORPORAL, "Corporal Verified"), (CODE, "OmniaForge"), (FUNNEL, "OmniaEngine")])
    def test_minors_blocked_from_adult_modules(self, band, msg, mod):
        r = KeywordRouter(auth_checker=lambda c: True).route(msg, ctx(band))
        assert r.should_route is False and r.age_restricted_module == mod

    def test_unknown_band_blocks_all_modules(self):
        r = KeywordRouter().route(NUTRI, OmniaContext("u", 0.1, "s"))  # age_band por defecto ""
        assert r.should_route is False
        assert r.age_restricted_module == "NutriVida"

    def test_age_gate_runs_before_elevated_auth(self):
        called = []
        r = KeywordRouter(auth_checker=lambda c: called.append(1) or True).route(CORPORAL, ctx("minor_basic"))
        assert r.age_restricted_module == "Corporal Verified"
        assert called == []  # ni siquiera se consulta la verificación

    def test_handle_is_never_called_for_restricted_modules(self):
        class Spy(OmniaModule):
            hits = 0

            @property
            def name(self):
                return "Spy"

            def keywords(self):
                return ["palabra espia"]

            def handle(self, message, context):
                Spy.hits += 1
                return ModuleResponse(text="x", module_name="Spy")

        router = KeywordRouter()
        router.modules.append(Spy())
        router.policy["Spy"] = "adult"
        r = router.route("palabra espia", ctx("minor_basic"))
        assert r.should_route is False and Spy.hits == 0
        r = router.route("palabra espia", ctx("adult"))
        assert r.should_route is True and Spy.hits == 1

    def test_restricted_best_module_is_not_rerouted_to_a_weaker_one(self):
        # Mensaje que mezcla: gana el módulo con más coincidencias; si está
        # restringido NO se cae a otro módulo de menor puntaje.
        msg = "ejecutar codigo en el sandbox con un script python y calorías"
        r = KeywordRouter().route(msg, ctx("minor"))
        assert r.should_route is False and r.age_restricted_module == "OmniaForge"

    def test_policy_is_per_instance(self):
        a, b = KeywordRouter(), KeywordRouter()
        a.policy["NutriVida"] = "adult"
        assert b.policy["NutriVida"] == "minor"
        assert policy.MODULE_MIN_AGE_BAND["NutriVida"] == "minor"


class TestRouteOrNone:
    def setup_method(self):
        set_auth_checker(None)

    def test_default_band_is_closed(self):
        out = route_or_none(NUTRI, user_id="u", consciousness_level=0.1, session_id="s")
        assert out is not None and out["age_restricted"] is True

    def test_restricted_dict_shape(self):
        out = route_or_none(GYM, user_id="u", consciousness_level=0.1, session_id="s", age_band="minor")
        assert out["age_restricted"] is True
        assert out["auth_required"] is False
        assert out["module"] == "OmniaAthletics"
        assert out["data"] is None
        assert "no está disponible" in out["response"]

    def test_allowed_dict_has_age_restricted_false(self):
        out = route_or_none(NUTRI, user_id="u", consciousness_level=0.1, session_id="s", age_band="adult")
        assert out["age_restricted"] is False and out["module"] == "NutriVida"

    def test_casual_chat_still_returns_none(self):
        assert route_or_none("Hola, ¿cómo estás?", user_id="u", consciousness_level=0.1,
                             session_id="s", age_band="minor") is None
        assert route_or_none("Hola, ¿cómo estás?", user_id="u", consciousness_level=0.1,
                             session_id="s") is None

    def test_corporal_adult_without_verification_asks_for_it(self):
        out = route_or_none(CORPORAL, user_id="u", consciousness_level=0.1, session_id="s", age_band="adult")
        assert out["auth_required"] is True and out["age_restricted"] is False
