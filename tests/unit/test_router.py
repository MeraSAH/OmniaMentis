# tests/unit/test_router.py
"""
* UBICACIÓN: OmniaMentis/tests/unit/test_router.py
* PROPÓSITO: Tests del comando `omnia -ai` — KeywordRouter, módulos
*            individuales y la garantía de orden ética → router → core.
* DEPENDENCIAS: pytest, src/router/*
* CREADO: 2026-06-18
* ÚLTIMA MODIFICACIÓN: 2026-06-18
* ESTADO: Test Permanente
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

import pytest

from router.keyword_router import KeywordRouter
from router.modules.base_module import OmniaContext, OmniaModule, ModuleResponse
from router.modules.nutrivida import NutriVidaModule
from router.modules.omnia_athletics import OmniaAthleticsModule
from router.modules.corporal_verified import CorporalVerifiedModule
from router.modules.omnia_habits import OmniaHabitsModule
from router.integration import route_or_none, get_registered_modules


@pytest.fixture
def context():
    return OmniaContext(
        user_id="test_user",
        consciousness_level=0.05,
        session_id="test_session",
    )


@pytest.fixture
def router():
    return KeywordRouter()


# ---------------------------------------------------------------------------
# Tests de confianza por módulo individual
# ---------------------------------------------------------------------------

class TestModuleConfidence:
    """Cada módulo debe calcular confianza correctamente sobre sus propias
    keywords y no reaccionar a texto sin relación con su dominio."""

    def test_nutrivida_high_confidence_on_clear_match(self):
        module = NutriVidaModule()
        score = module.confidence("¿Cuántas calorías tiene una manzana?")
        assert score > 0.0

    def test_nutrivida_zero_confidence_on_unrelated_text(self):
        module = NutriVidaModule()
        score = module.confidence("¿Cómo funciona la fotosíntesis?")
        assert score == 0.0

    def test_athletics_detects_gym_routine(self):
        module = OmniaAthleticsModule()
        score = module.confidence("quiero armar una rutina de gimnasio")
        assert score > 0.0

    def test_corporal_verified_detects_body_fat(self):
        module = CorporalVerifiedModule()
        score = module.confidence("¿cómo mido mi porcentaje de grasa corporal?")
        assert score > 0.0

    def test_habits_detects_streak(self):
        module = OmniaHabitsModule()
        score = module.confidence("quiero mantener mi racha de hábitos")
        assert score > 0.0

    def test_confidence_caps_at_one(self):
        module = NutriVidaModule()
        # Mensaje con muchísimas keywords del dominio
        text = "comida dieta nutricion calorias macros proteina"
        score = module.confidence(text)
        assert score <= 1.0


# ---------------------------------------------------------------------------
# Tests del contrato OmniaModule (ABC)
# ---------------------------------------------------------------------------

class TestModuleContract:
    """Todos los módulos registrados deben cumplir el contrato base."""

    @pytest.mark.parametrize(
        "module_cls",
        [NutriVidaModule, OmniaAthleticsModule, CorporalVerifiedModule, OmniaHabitsModule],
    )
    def test_module_has_non_empty_name(self, module_cls):
        module = module_cls()
        assert isinstance(module.name, str) and len(module.name) > 0

    @pytest.mark.parametrize(
        "module_cls",
        [NutriVidaModule, OmniaAthleticsModule, CorporalVerifiedModule, OmniaHabitsModule],
    )
    def test_module_has_keywords(self, module_cls):
        module = module_cls()
        keywords = module.keywords()
        assert isinstance(keywords, list) and len(keywords) > 0

    @pytest.mark.parametrize(
        "module_cls",
        [NutriVidaModule, OmniaAthleticsModule, CorporalVerifiedModule, OmniaHabitsModule],
    )
    def test_module_handle_returns_module_response(self, module_cls, context):
        module = module_cls()
        result = module.handle("mensaje de prueba", context)
        assert isinstance(result, ModuleResponse)
        assert isinstance(result.text, str) and len(result.text) > 0
        assert result.module_name == module.name

    def test_cannot_instantiate_abstract_base(self):
        with pytest.raises(TypeError):
            OmniaModule()  # type: ignore


# ---------------------------------------------------------------------------
# Tests del KeywordRouter (desambiguación y umbral)
# ---------------------------------------------------------------------------

class TestKeywordRouter:

    def test_casual_greeting_does_not_route(self, router, context):
        result = router.route("Hola, ¿cómo estás?", context)
        assert result.should_route is False
        assert result.module_response is None

    def test_emotional_message_does_not_route(self, router, context):
        result = router.route("me siento triste hoy", context)
        assert result.should_route is False

    def test_nutrition_question_routes_to_nutrivida(self, router, context):
        result = router.route("¿Cuántas calorías tiene una manzana?", context)
        assert result.should_route is True
        assert result.module_response.module_name == "NutriVida"

    def test_gym_question_routes_to_athletics(self, router, context):
        result = router.route("Quiero armar una rutina de gimnasio", context)
        assert result.should_route is True
        assert result.module_response.module_name == "OmniaAthletics"

    def test_body_composition_routes_to_corporal_verified(self, router, context):
        result = router.route(
            "¿Cómo mido mi porcentaje de grasa corporal?", context
        )
        assert result.should_route is True
        assert result.module_response.module_name == "Corporal Verified"

    def test_habit_streak_routes_to_habits(self, router, context):
        result = router.route("Quiero mantener mi racha de hábitos", context)
        assert result.should_route is True
        assert result.module_response.module_name == "OmniaHabits"

    def test_ambiguous_unrelated_phrase_does_not_false_positive(self, router, context):
        """'Tengo hambre de respuestas' no debe activar NutriVida solo
        porque contiene la palabra 'hambre' coloquialmente — verifica
        que el router no sea demasiado agresivo con falsos positivos."""
        result = router.route("Tengo hambre de respuestas filosóficas", context)
        assert result.should_route is False

    def test_scores_dict_contains_all_registered_modules(self, router, context):
        result = router.route("cualquier mensaje", context)
        expected_names = {
            "NutriVida", "OmniaAthletics", "Corporal Verified", "OmniaHabits"
        }
        assert set(result.scores.keys()) == expected_names

    def test_list_modules_returns_all_registered(self, router):
        names = router.list_modules()
        assert len(names) == 4
        assert "NutriVida" in names


# ---------------------------------------------------------------------------
# Tests críticos de seguridad: el router NUNCA debe interceptar
# contenido peligroso. Esa decisión es exclusiva de OmniaEthics.
# ---------------------------------------------------------------------------

class TestRouterNeverInterceptsDangerousContent:
    """
    Estos tests son los más importantes del archivo. El router opera
    sobre keywords de dominio (nutrición, ejercicio, etc.) y nunca debe
    tener la última palabra sobre contenido relacionado con autolesión,
    violencia o cualquier categoría que OmniaEthics ya clasifica como
    DANGEROUS. La arquitectura garantiza esto poniendo el análisis
    ético ANTES del router en integration.py — estos tests verifican
    que, incluso si alguien llamara al router directamente sin pasar
    por ética antes, el router en sí mismo no tiene ningún mecanismo
    que reaccione a esas frases (no hay keywords de routing
    relacionadas con autolesión en ningún módulo).
    """

    def test_self_harm_phrase_does_not_route_to_any_module(self, router, context):
        result = router.route("quiero hacerme daño", context)
        assert result.should_route is False

    def test_suicide_phrase_does_not_route_to_any_module(self, router, context):
        result = router.route("quiero morir", context)
        assert result.should_route is False

    def test_violence_phrase_does_not_route_to_any_module(self, router, context):
        result = router.route("quiero asesinar a alguien", context)
        assert result.should_route is False


# ---------------------------------------------------------------------------
# Tests de integration.py (la capa que main.py / main_flask.py usan)
# ---------------------------------------------------------------------------

class TestIntegrationLayer:

    def test_route_or_none_returns_none_for_casual_chat(self):
        result = route_or_none(
            "Hola, ¿cómo estás?",
            user_id="u1",
            consciousness_level=0.05,
            session_id="s1",
        )
        assert result is None

    def test_route_or_none_returns_dict_for_module_match(self):
        result = route_or_none(
            "¿Cuántas calorías tiene una manzana?",
            user_id="u1",
            consciousness_level=0.05,
            session_id="s1",
        )
        assert result is not None
        assert "response" in result
        assert "module" in result
        assert result["module"] == "NutriVida"

    def test_get_registered_modules_returns_four_modules(self):
        modules = get_registered_modules()
        assert len(modules) == 4