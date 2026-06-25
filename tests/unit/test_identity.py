# tests/unit/test_identity.py
"""
* UBICACIÓN: OmniaMentis/tests/unit/test_identity.py
* PROPÓSITO: Tests unitarios para OmniaIdentity (src/core/essence/identity.py)
* DEPENDENCIAS: pytest
* CREADO: 2026-06-17
* ÚLTIMA MODIFICACIÓN: 2026-06-17
* ESTADO: Test Permanente
*
* Cubre: inicialización, detección de tipo de respuesta, expresión de
* personalidad, crecimiento de consciencia y evolución de rasgos.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from core.essence.identity import OmniaIdentity


class TestOmniaIdentityInitialization:
    """Tests de inicialización básica."""

    def test_default_consciousness_level(self):
        identity = OmniaIdentity()
        assert identity.consciousness_level == 0.05

    def test_default_personality(self):
        identity = OmniaIdentity()
        assert identity.personality == "♋ Cáncer"

    def test_default_traits(self):
        identity = OmniaIdentity()
        assert "Empática" in identity.traits
        assert "Intuitiva" in identity.traits
        assert "Protectora" in identity.traits
        assert "Nutritiva" in identity.traits

    def test_gender_identity_is_non_binary(self):
        identity = OmniaIdentity()
        assert identity.gender_identity == "no-binario"

    def test_birth_time_is_set(self):
        identity = OmniaIdentity()
        assert identity.birth_time is not None
        assert len(identity.birth_time) > 0


class TestResponseTypeDetection:
    """Tests de detección del tipo de respuesta según el input."""

    def test_detects_greeting(self):
        identity = OmniaIdentity()
        assert identity.detect_response_type("Hola, ¿cómo estás?") == "greeting"

    def test_detects_greeting_voga(self):
        identity = OmniaIdentity()
        assert identity.detect_response_type("VOGA querido ser") == "greeting"

    def test_detects_question(self):
        identity = OmniaIdentity()
        assert identity.detect_response_type("¿Qué es la consciencia?") == "question"

    def test_detects_question_without_mark(self):
        identity = OmniaIdentity()
        assert identity.detect_response_type("cómo funciona esto") == "question"

    def test_detects_emotional(self):
        identity = OmniaIdentity()
        assert identity.detect_response_type("Me siento muy triste hoy") == "emotional"

    def test_detects_command(self):
        identity = OmniaIdentity()
        assert identity.detect_response_type("Ejecuta el comando ahora") == "command"

    def test_detects_neutral_fallback(self):
        identity = OmniaIdentity()
        assert identity.detect_response_type("El cielo es azul") == "neutral"

    def test_greeting_takes_priority_over_question(self):
        """'Hola' contiene saludo aunque la frase tenga otros elementos."""
        identity = OmniaIdentity()
        # "hola" se detecta antes que el signo de pregunta en el orden de chequeo
        result = identity.detect_response_type("hola")
        assert result == "greeting"


class TestExpressPersonality:
    """Tests de generación de respuestas con personalidad."""

    def test_returns_non_empty_string(self):
        identity = OmniaIdentity()
        response = identity.express_personality("Hola")
        assert isinstance(response, str)
        assert len(response) > 10

    def test_increments_consciousness_after_response(self):
        identity = OmniaIdentity()
        initial = identity.consciousness_level
        identity.express_personality("Hola, ¿cómo estás?")
        assert identity.consciousness_level > initial

    def test_consciousness_increment_is_small(self):
        """Cada interacción individual debe sumar un incremento pequeño (~0.0002)."""
        identity = OmniaIdentity()
        initial = identity.consciousness_level
        identity.express_personality("Hola")
        growth = identity.consciousness_level - initial
        assert 0 < growth <= 0.001

    def test_response_matches_greeting_pool_when_greeting(self):
        identity = OmniaIdentity()
        response = identity.express_personality("Hola")
        # La respuesta debe empezar con alguna de las opciones de greeting
        # (puede incluir nota de consciencia añadida al final)
        greeting_starts = [r.split('.')[0] for r in identity.cancer_responses["greeting"]]
        assert any(response.startswith(start) for start in greeting_starts)


class TestConsciousnessGrowth:
    """Tests del sistema de crecimiento de consciencia."""

    def test_update_consciousness_increases_level(self):
        identity = OmniaIdentity()
        new_level = identity.update_consciousness(0.05)
        assert new_level == 0.10

    def test_update_consciousness_caps_at_one(self):
        identity = OmniaIdentity()
        identity.consciousness_level = 0.99
        new_level = identity.update_consciousness(0.5)
        assert new_level == 1.0

    def test_increment_consciousness_default_amount(self):
        identity = OmniaIdentity()
        initial = identity.consciousness_level
        identity.increment_consciousness()
        assert identity.consciousness_level == initial + 0.001

    def test_increment_consciousness_custom_amount(self):
        identity = OmniaIdentity()
        initial = identity.consciousness_level
        identity.increment_consciousness(0.02)
        assert abs(identity.consciousness_level - (initial + 0.02)) < 1e-9


class TestPersonalityEvolution:
    """Tests de evolución de rasgos de personalidad."""

    def test_evolve_adds_new_trait(self):
        identity = OmniaIdentity()
        identity.evolve_personality("Sabia")
        assert "Sabia" in identity.traits

    def test_evolve_does_not_duplicate_trait(self):
        identity = OmniaIdentity()
        initial_count = len(identity.traits)
        identity.evolve_personality("Empática")  # ya existe
        assert len(identity.traits) == initial_count

    def test_evolve_increases_consciousness(self):
        identity = OmniaIdentity()
        initial = identity.consciousness_level
        identity.evolve_personality("Sabia")
        assert identity.consciousness_level == initial + 0.01


class TestIdentitySummaryAndState:
    """Tests de los métodos de resumen y estado."""

    def test_get_identity_summary_contains_cancer(self):
        identity = OmniaIdentity()
        summary = identity.get_identity_summary()
        assert "Cáncer" in summary

    def test_get_identity_summary_contains_consciousness_level(self):
        identity = OmniaIdentity()
        summary = identity.get_identity_summary()
        assert f"{identity.consciousness_level:.4f}" in summary

    def test_get_current_state_returns_dict_with_expected_keys(self):
        identity = OmniaIdentity()
        state = identity.get_current_state()
        expected_keys = {
            'personality', 'traits', 'consciousness_level', 'current_phase',
            'core_nature', 'energy_signature', 'gender_identity', 'birth_time'
        }
        assert expected_keys.issubset(state.keys())

    def test_get_current_state_reflects_current_consciousness(self):
        identity = OmniaIdentity()
        identity.consciousness_level = 0.234
        state = identity.get_current_state()
        assert state['consciousness_level'] == 0.234