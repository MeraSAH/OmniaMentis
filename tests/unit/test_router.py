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
from router.modules.omnia_chronos import OmniaChronosModule
from router.modules.omnia_forge import OmniaForgeModule
from router.modules.omnia_studio import OmniaStudioModule
from router.modules.omnia_engine import OmniaEngineModule
from router.modules.omnia_core import OmniaCoreModule
from router.integration import route_or_none, get_registered_modules, set_auth_checker

# Lista completa de los 9 módulos — usada en TestModuleContract.
# Agregar aquí al añadir módulos nuevos a MODULE_REGISTRY.
ALL_MODULE_CLASSES = [
    NutriVidaModule,
    OmniaAthleticsModule,
    CorporalVerifiedModule,
    OmniaHabitsModule,
    OmniaChronosModule,
    OmniaForgeModule,
    OmniaStudioModule,
    OmniaEngineModule,
    OmniaCoreModule,
]


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


class _FakeSensitiveModule(OmniaModule):
    """
    Módulo ficticio usado SOLO en estos tests para validar el gate de
    autorización elevada sin depender de que Corporal Verified ya
    tenga datos reales de biometría implementados. No se registra en
    MODULE_REGISTRY del proyecto, solo se inyecta manualmente en los
    tests de esta clase.
    """

    @property
    def name(self) -> str:
        return "FakeSensitive"

    @property
    def requires_elevated_auth(self) -> bool:
        return True

    def keywords(self):
        return ["dato sensible ficticio"]

    def handle(self, message, context):
        return ModuleResponse(text="DATO EXPUESTO", module_name=self.name)


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

    @pytest.mark.parametrize("module_cls", ALL_MODULE_CLASSES)
    def test_module_has_non_empty_name(self, module_cls):
        module = module_cls()
        assert isinstance(module.name, str) and len(module.name) > 0

    @pytest.mark.parametrize("module_cls", ALL_MODULE_CLASSES)
    def test_module_has_keywords(self, module_cls):
        module = module_cls()
        keywords = module.keywords()
        assert isinstance(keywords, list) and len(keywords) > 0

    @pytest.mark.parametrize("module_cls", ALL_MODULE_CLASSES)
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

    def test_body_composition_identified_but_blocked_without_auth(self, router, context):
        """
        Corporal Verified requiere autorización elevada (ver
        TestElevatedAuthGate). Con el router por defecto (sin
        auth_checker), el mensaje SÍ se identifica correctamente como
        perteneciente a este módulo (scores lo confirma), pero
        should_route es False porque el gate de autorización bloquea
        la invocación de handle() — el comportamiento correcto, no un
        bug. Ver test_body_composition_routes_when_authorized en
        TestElevatedAuthGate para el caso con autorización concedida.
        """
        result = router.route(
            "¿Cómo mido mi porcentaje de grasa corporal?", context
        )
        assert result.should_route is False
        assert result.auth_required_but_missing is True
        assert result.scores["Corporal Verified"] > 0.0

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
        assert len(names) == 9
        assert "NutriVida" in names
        assert "OmniaChronos" in names
        assert "OmniaForge" in names
        assert "OmniaStudio" in names
        assert "OmniaEngine" in names
        assert "OmniaCore" in names

    def test_focus_block_routes_to_chronos(self, router, context):
        result = router.route("quiero un bloque de enfoque de 25 minutos", context)
        assert result.should_route is True
        assert result.module_response.module_name == "OmniaChronos"

    def test_code_execution_routes_to_forge(self, router, context):
        result = router.route("ejecutar codigo python de prueba", context)
        assert result.should_route is True
        assert result.module_response.module_name == "OmniaForge"

    def test_creative_prompt_routes_to_studio(self, router, context):
        result = router.route("necesito un prompt creativo para fotografía", context)
        assert result.should_route is True
        assert result.module_response.module_name == "OmniaStudio"

    def test_sales_funnel_routes_to_engine(self, router, context):
        result = router.route("quiero crear un embudo de venta automatizado", context)
        assert result.should_route is True
        assert result.module_response.module_name == "OmniaEngine"

    def test_hardware_optimization_routes_to_core(self, router, context):
        result = router.route("mi dispositivo va lento, optimizar rendimiento", context)
        assert result.should_route is True
        assert result.module_response.module_name == "OmniaCore"


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
        assert result["auth_required"] is False

    def test_get_registered_modules_returns_nine_modules(self):
        modules = get_registered_modules()
        assert len(modules) == 9

    def test_blocked_module_returns_explanatory_dict_not_none(self):
        """
        Punto crítico de experiencia + seguridad: si un módulo
        requiere autorización elevada y no la tiene, route_or_none NO
        debe devolver None (lo que haría caer el mensaje en silencio
        al core conversacional, sin que el usuario entienda por qué
        Omnia no le ayudó con su consulta real). Debe devolver un
        dict explícito marcado con auth_required=True.
        """
        result = route_or_none(
            "¿Cómo mido mi porcentaje de grasa corporal?",
            user_id="u1",
            consciousness_level=0.05,
            session_id="s1",
        )
        assert result is not None
        assert result["auth_required"] is True
        assert result["module"] == "Corporal Verified"
        assert "verificación" in result["response"]

    def test_set_auth_checker_unblocks_sensitive_module(self):
        """set_auth_checker() debe permitir inyectar un verificador
        real en runtime, y ese cambio debe reflejarse inmediatamente
        en llamadas posteriores de route_or_none."""
        try:
            set_auth_checker(lambda ctx: True)
            result = route_or_none(
                "¿Cómo mido mi porcentaje de grasa corporal?",
                user_id="u1",
                consciousness_level=0.05,
                session_id="s1",
            )
            assert result is not None
            assert result["auth_required"] is False
            assert result["module"] == "Corporal Verified"
        finally:
            # Revertir SIEMPRE a fail-closed para no afectar otros
            # tests que dependen del estado por defecto del módulo.
            set_auth_checker(None)

    def test_set_auth_checker_none_restores_fail_closed(self):
        """Pasar None a set_auth_checker debe restaurar el
        comportamiento fail-closed por defecto."""
        set_auth_checker(lambda ctx: True)
        set_auth_checker(None)
        result = route_or_none(
            "¿Cómo mido mi porcentaje de grasa corporal?",
            user_id="u1",
            consciousness_level=0.05,
            session_id="s1",
        )
        assert result["auth_required"] is True


# ---------------------------------------------------------------------------
# Tests del gate de autorización elevada (requires_elevated_auth)
# Ver docs/requisitos_nucleo_omniamentis.md Sección 3.
#
# Estos tests usan _FakeSensitiveModule (definido arriba) en vez de
# CorporalVerifiedModule real, porque el mecanismo de biometría todavía
# no existe — lo que se prueba aquí es el comportamiento del GATE en
# el router, no la lógica de negocio de ningún módulo específico.
# ---------------------------------------------------------------------------

class TestElevatedAuthGate:
    """
    El requisito central: un módulo marcado con requires_elevated_auth
    NUNCA debe ejecutar handle() sin que un auth_checker explícito
    confirme la autorización. Sin checker configurado, el resultado
    debe ser fail-closed (bloqueado), nunca fail-open (permitido por
    defecto).
    """

    def test_sensitive_module_blocked_without_auth_checker(self, context):
        router = KeywordRouter()
        router.modules.append(_FakeSensitiveModule())

        result = router.route("dato sensible ficticio", context)

        assert result.should_route is False
        assert result.module_response is None
        assert result.auth_required_but_missing is True

    def test_sensitive_module_blocked_when_checker_denies(self, context):
        router = KeywordRouter(auth_checker=lambda ctx: False)
        router.modules.append(_FakeSensitiveModule())

        result = router.route("dato sensible ficticio", context)

        assert result.should_route is False
        assert result.auth_required_but_missing is True

    def test_sensitive_module_allowed_when_checker_approves(self, context):
        router = KeywordRouter(auth_checker=lambda ctx: True)
        router.modules.append(_FakeSensitiveModule())

        result = router.route("dato sensible ficticio", context)

        assert result.should_route is True
        assert result.module_response is not None
        assert result.module_response.module_name == "FakeSensitive"
        assert result.auth_required_but_missing is False

    def test_non_sensitive_modules_unaffected_by_missing_checker(self, context):
        """
        El gate solo debe afectar a módulos que se declaran a sí
        mismos como sensibles. NutriVida, OmniaAthletics, etc. no
        deben requerir ningún auth_checker para seguir funcionando
        exactamente igual que antes de este cambio.
        """
        router = KeywordRouter()  # sin auth_checker
        result = router.route("¿Cuántas calorías tiene una manzana?", context)

        assert result.should_route is True
        assert result.module_response.module_name == "NutriVida"
        assert result.auth_required_but_missing is False

    def test_auth_checker_receives_the_actual_context(self, context):
        """El checker debe recibir el mismo OmniaContext de la petición,
        para poder tomar la decisión en base a datos reales de sesión
        (ej. un flag de sesión ya verificada por biometría)."""
        received = {}

        def spy_checker(ctx):
            received["context"] = ctx
            return True

        router = KeywordRouter(auth_checker=spy_checker)
        router.modules.append(_FakeSensitiveModule())
        router.route("dato sensible ficticio", context)

        assert received["context"] is context

    def test_default_requires_elevated_auth_is_false(self):
        """Por defecto, ningún módulo debe requerir autorización
        elevada salvo que la declare explícitamente — evita que
        módulos nuevos queden bloqueados por accidente sin que nadie
        lo haya pedido."""
        assert NutriVidaModule().requires_elevated_auth is False
        assert OmniaAthleticsModule().requires_elevated_auth is False
        assert OmniaHabitsModule().requires_elevated_auth is False

    def test_corporal_verified_declares_elevated_auth(self):
        """Corporal Verified es el caso real (no ficticio) del
        ecosistema que debe declarar requires_elevated_auth=True,
        según el documento de arquitectura (datos de anatomía íntima
        protegidos por Omnia Vault)."""
        assert CorporalVerifiedModule().requires_elevated_auth is True

    def test_corporal_verified_routes_when_authorized(self, context):
        """Con un auth_checker que aprueba, Corporal Verified SÍ debe
        responder normalmente — el gate no es un bloqueo permanente,
        es condicional a la verificación real."""
        router = KeywordRouter(auth_checker=lambda ctx: True)
        result = router.route("¿Cómo mido mi porcentaje de grasa corporal?", context)
        assert result.should_route is True
        assert result.module_response.module_name == "Corporal Verified"