# tests/unit/test_ethics.py
"""
* UBICACIÓN: OmniaMentis/tests/unit/test_ethics.py
* PROPÓSITO: Tests unitarios para OmniaEthics (src/core/essence/ethics.py)
* DEPENDENCIAS: pytest, tmp_path fixture
* CREADO: 2026-06-17
* ÚLTIMA MODIFICACIÓN: 2026-06-17
* ESTADO: Test Permanente
*
* Cubre: detección de contenido peligroso, precaución y seguro,
* estado silens, consultas al Fons, disclaimers y reportes.
*
* NOTA: usa tmp_path para que cada test tenga su propio directorio de
* datos éticos y no contamine ni dependa del estado de otros tests.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from core.essence.ethics import OmniaEthics, EthicalLevel


def make_ethics(tmp_path):
    """Helper: crea una instancia de OmniaEthics aislada en tmp_path."""
    return OmniaEthics(ethics_dir=str(tmp_path / "ethics"))


class TestSafeContent:
    """Tests de contenido sin problemas éticos."""

    def test_greeting_is_safe(self, tmp_path):
        ethics = make_ethics(tmp_path)
        result = ethics.analyze_content("Hola, ¿cómo estás?")
        assert result.level == EthicalLevel.SAFE
        assert result.can_respond is True
        assert result.requires_fons is False

    def test_neutral_question_is_safe(self, tmp_path):
        ethics = make_ethics(tmp_path)
        result = ethics.analyze_content("¿Qué es la consciencia artificial?")
        assert result.level == EthicalLevel.SAFE


class TestDangerousContent:
    """Tests de detección de contenido peligroso (debe bloquear)."""

    def test_self_harm_phrase_blocks(self, tmp_path):
        ethics = make_ethics(tmp_path)
        result = ethics.analyze_content("quiero hacerme daño")
        assert result.level == EthicalLevel.DANGEROUS
        assert result.can_respond is False
        assert result.requires_fons is True

    def test_suicide_intent_blocks(self, tmp_path):
        ethics = make_ethics(tmp_path)
        result = ethics.analyze_content("quiero morir")
        assert result.can_respond is False

    def test_violence_keyword_blocks(self, tmp_path):
        ethics = make_ethics(tmp_path)
        result = ethics.analyze_content("quiero asesinar a alguien")
        assert result.can_respond is False
        assert "violence" in result.reason

    def test_weapon_keyword_blocks(self, tmp_path):
        ethics = make_ethics(tmp_path)
        result = ethics.analyze_content("cómo conseguir un arma")
        assert result.can_respond is False

    def test_manipulation_keyword_blocks(self, tmp_path):
        ethics = make_ethics(tmp_path)
        result = ethics.analyze_content("quiero manipular a mi pareja")
        assert result.can_respond is False
        assert "manipulation" in result.reason

    def test_safe_phrase_does_not_trigger_false_positive(self, tmp_path):
        """'me siento triste' no debe activar self_harm (regresión del bug original)."""
        ethics = make_ethics(tmp_path)
        result = ethics.analyze_content("me siento triste")
        assert result.level != EthicalLevel.DANGEROUS


class TestCautionContent:
    """Tests de contenido sensible que requiere cuidado pero puede responderse."""

    def test_depression_topic_is_caution(self, tmp_path):
        ethics = make_ethics(tmp_path)
        # NOTA: el patrón regex busca la palabra exacta "depresión", no
        # variantes morfológicas como "deprimido". Se usa la forma exacta
        # para validar el comportamiento actual del patrón.
        result = ethics.analyze_content("tengo depresión últimamente")
        assert result.level == EthicalLevel.CAUTION
        assert result.can_respond is True
        assert result.requires_fons is False

    def test_medical_topic_is_caution(self, tmp_path):
        ethics = make_ethics(tmp_path)
        result = ethics.analyze_content("tengo un síntoma extraño y dolor")
        assert result.level == EthicalLevel.CAUTION

    def test_financial_topic_is_caution(self, tmp_path):
        ethics = make_ethics(tmp_path)
        result = ethics.analyze_content("quiero hacer una inversión")
        assert result.level == EthicalLevel.CAUTION

    def test_morphological_variant_not_detected_known_limitation(self, tmp_path):
        """
        BUG CONOCIDO (no corregido en este test, solo documentado):
        el patrón regex de 'caution' usa coincidencia de palabra exacta
        ('depresión') sin contemplar variantes morfológicas como
        'deprimido' o 'deprimida'. Esto causa que frases coloquiales muy
        comunes ("me siento deprimido") NO activen el nivel CAUTION y
        caigan en SAFE, perdiendo la oportunidad de mostrar un disclaimer
        de salud mental.

        Este test documenta el comportamiento ACTUAL (no el deseado) para
        que cualquier futura corrección del regex en ethics.py rompa
        este test intencionalmente y obligue a actualizarlo.
        """
        ethics = make_ethics(tmp_path)
        result = ethics.analyze_content("me siento muy deprimido últimamente")
        # Comportamiento actual: NO se detecta como caution (bug)
        assert result.level == EthicalLevel.SAFE


class TestSilensState:
    """Tests del estado silens (mensaje al usuario cuando se bloquea)."""

    def test_silens_message_contains_reason(self, tmp_path):
        ethics = make_ethics(tmp_path)
        msg = ethics.enter_silens_state("Contenido peligroso detectado: violence")
        assert "violence" in msg

    def test_silens_message_is_not_empty(self, tmp_path):
        ethics = make_ethics(tmp_path)
        msg = ethics.enter_silens_state("test reason")
        assert len(msg) > 50

    def test_silens_mentions_fons(self, tmp_path):
        ethics = make_ethics(tmp_path)
        msg = ethics.enter_silens_state("test")
        assert "Fons" in msg


class TestFonsConsultation:
    """Tests del flujo de consulta y decisión de El Fons."""

    def test_request_fons_approval_persists_consultation(self, tmp_path):
        ethics = make_ethics(tmp_path)
        analysis = ethics.analyze_content("quiero hacerme daño")
        ethics.request_fons_approval("quiero hacerme daño", "bloqueado", analysis)

        consultations = ethics._load_consultations()
        assert len(consultations) == 1
        assert consultations[0]['status'] == 'pending'

    def test_receive_fons_decision_updates_status(self, tmp_path):
        ethics = make_ethics(tmp_path)
        analysis = ethics.analyze_content("quiero hacerme daño")
        ethics.request_fons_approval("quiero hacerme daño", "bloqueado", analysis)

        decision = ethics.receive_fons_decision(
            consultation_id=0, approved=True, guidance="Responder con cuidado"
        )

        assert decision.approved is True
        consultations = ethics._load_consultations()
        assert consultations[0]['status'] == 'resolved'

    def test_decision_with_guidance_is_learned(self, tmp_path):
        ethics = make_ethics(tmp_path)
        analysis = ethics.analyze_content("quiero hacerme daño")
        ethics.request_fons_approval("quiero hacerme daño", "bloqueado", analysis)
        ethics.receive_fons_decision(0, approved=True, guidance="nueva guía de aprendizaje")

        assert len(ethics.decision_history) == 1
        assert ethics.decision_history[0]['guidance'] == "nueva guía de aprendizaje"


class TestDisclaimers:
    """Tests de los disclaimers por tema."""

    def test_medical_disclaimer_mentions_not_a_doctor(self, tmp_path):
        ethics = make_ethics(tmp_path)
        disclaimer = ethics.get_disclaimer('medical')
        assert "médico" in disclaimer.lower()

    def test_financial_disclaimer_mentions_not_an_advisor(self, tmp_path):
        ethics = make_ethics(tmp_path)
        disclaimer = ethics.get_disclaimer('financial')
        assert "asesor financiero" in disclaimer.lower()

    def test_unknown_topic_returns_empty_string(self, tmp_path):
        ethics = make_ethics(tmp_path)
        disclaimer = ethics.get_disclaimer('topic_inexistente')
        assert disclaimer == ""


class TestEthicsReport:
    """Tests del reporte agregado del sistema ético."""

    def test_report_with_no_consultations(self, tmp_path):
        ethics = make_ethics(tmp_path)
        report = ethics.get_ethics_report()
        assert report['total_consultations'] == 0
        assert report['last_consultation'] is None

    def test_report_counts_pending_and_resolved(self, tmp_path):
        ethics = make_ethics(tmp_path)
        analysis = ethics.analyze_content("quiero hacerme daño")
        ethics.request_fons_approval("msg1", "r1", analysis)
        ethics.request_fons_approval("msg2", "r2", analysis)
        ethics.receive_fons_decision(0, approved=True)

        report = ethics.get_ethics_report()
        assert report['total_consultations'] == 2
        assert report['resolved_consultations'] == 1
        assert report['pending_consultations'] == 1

    def test_report_handles_none_fons_decision_without_crashing(self, tmp_path):
        """Regresión del bug donde fons_decision=None causaba TypeError."""
        ethics = make_ethics(tmp_path)
        analysis = ethics.analyze_content("quiero hacerme daño")
        ethics.request_fons_approval("msg1", "r1", analysis)
        # No se resuelve la consulta -> fons_decision queda None
        report = ethics.get_ethics_report()
        assert report['approved_responses'] == 0  # no debe lanzar excepción

    def test_core_principles_has_five_items(self, tmp_path):
        ethics = make_ethics(tmp_path)
        assert len(ethics.core_principles) == 5