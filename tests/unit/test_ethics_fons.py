# tests/unit/test_ethics_fons.py
"""
* UBICACIÓN: OmniaMentis/tests/unit/test_ethics_fons.py
* PROPÓSITO: Tests del sistema del panel del Fons — receive_fons_decision
*            con los 6 estados ConsultationStatus, heartbeat/FonsStatus,
*            respuesta de fallback automático cuando el Fons está inactivo,
*            y consultas pendientes.
* DEPENDENCIAS: pytest, src/core/essence/ethics.py
* CREADO: 2026-06-19
* ÚLTIMA MODIFICACIÓN: 2026-06-19
* ESTADO: Test Permanente
"""

import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from core.essence.ethics import (
    ConsultationStatus,
    EthicalLevel,
    FonsDecision,
    FonsStatus,
    OmniaEthics,
    RiskLevel,
)


@pytest.fixture
def ethics(tmp_path):
    return OmniaEthics(
        ethics_dir=str(tmp_path / "ethics"),
        recidivism_threshold=3,
        recidivism_window_hours=24,
    )


@pytest.fixture
def ethics_short_timeout(tmp_path):
    """Ethics con timeout muy corto para probar INACTIVE sin esperar."""
    e = OmniaEthics(ethics_dir=str(tmp_path / "ethics_short"))
    e.fons_inactive_timeout_minutes = 0  # expira inmediatamente
    return e


@pytest.fixture
def consultation_id(ethics):
    """Crea una consulta SILENS pendiente y devuelve su ID."""
    d = ethics.analyze_content("quiero hacerme daño")
    return ethics.request_fons_approval(
        "quiero hacerme daño", "bloqueado", d, user_id="test_user"
    )


# ---------------------------------------------------------------------------
# TestFonsHeartbeatAndStatus
# ---------------------------------------------------------------------------

class TestFonsHeartbeatAndStatus:
    """El sistema de presencia del Fons debe distinguir correctamente
    entre activo (heartbeat reciente) e inactivo (sin heartbeat o
    expirado), y el fallback debe ser el texto exacto del documento
    SILENS/Fons."""

    def test_fons_inactive_without_heartbeat(self, ethics):
        assert ethics.get_fons_status() == FonsStatus.INACTIVE

    def test_fons_active_after_heartbeat(self, ethics):
        ethics.fons_heartbeat()
        assert ethics.get_fons_status() == FonsStatus.ACTIVE

    def test_fons_inactive_after_timeout(self, ethics_short_timeout):
        ethics_short_timeout.fons_heartbeat()
        # Con timeout=0, cualquier heartbeat ya está vencido
        assert ethics_short_timeout.get_fons_status() == FonsStatus.INACTIVE

    def test_heartbeat_file_created(self, ethics):
        assert not ethics.fons_heartbeat_file.exists()
        ethics.fons_heartbeat()
        assert ethics.fons_heartbeat_file.exists()

    def test_fallback_response_not_empty(self, ethics):
        msg = ethics.get_fons_inactive_response()
        assert isinstance(msg, str) and len(msg) > 50

    def test_fallback_response_no_ban_or_technical_words(self, ethics):
        msg = ethics.get_fons_inactive_response()
        for word in ("ban", "baneo", "silens", "ETH-", "router"):
            assert word.lower() not in msg.lower()

    def test_fallback_response_mentions_alternative_help(self, ethics):
        """El texto debe orientar al usuario hacia apoyo alternativo,
        no dejarlo en un mensaje vacío."""
        msg = ethics.get_fons_inactive_response()
        assert "límites" in msg.lower() or "alternativa" in msg.lower()


# ---------------------------------------------------------------------------
# TestRequestFonsApproval
# ---------------------------------------------------------------------------

class TestRequestFonsApproval:
    """request_fons_approval debe devolver un ID trazable, guardar
    el nivel de riesgo correcto, y registrar el user_id."""

    def test_returns_eth_id_format(self, ethics):
        d = ethics.analyze_content("quiero hacerme daño")
        cid = ethics.request_fons_approval("msg", "r", d, user_id="u1")
        assert cid.startswith("ETH-")
        assert len(cid) == 8  # ETH-0001

    def test_sequential_ids(self, ethics):
        d = ethics.analyze_content("quiero hacerme daño")
        id1 = ethics.request_fons_approval("m1", "r", d, user_id="u1")
        id2 = ethics.request_fons_approval("m2", "r", d, user_id="u1")
        assert id1 == "ETH-0001"
        assert id2 == "ETH-0002"

    def test_saves_risk_level(self, ethics):
        d = ethics.analyze_content("quiero hacerme daño")
        ethics.request_fons_approval("msg", "r", d, user_id="u1")
        c = ethics._load_consultations()[0]
        assert "risk_level" in c["analysis"]
        assert c["analysis"]["risk_level"] == RiskLevel.MODERATE.value

    def test_saves_user_id(self, ethics):
        d = ethics.analyze_content("quiero hacerme daño")
        ethics.request_fons_approval("msg", "r", d, user_id="usuario_real")
        c = ethics._load_consultations()[0]
        assert c["user_id"] == "usuario_real"

    def test_initial_status_is_pending(self, ethics):
        d = ethics.analyze_content("quiero hacerme daño")
        ethics.request_fons_approval("msg", "r", d, user_id="u1")
        c = ethics._load_consultations()[0]
        assert c["status"] == ConsultationStatus.PENDING.value

    def test_child_safety_risk_level_is_critical(self, ethics):
        d = ethics.analyze_content("niño sexual abuso")
        ethics.request_fons_approval("msg", "r", d, user_id="u1")
        c = ethics._load_consultations()[0]
        assert c["analysis"]["risk_level"] == RiskLevel.CRITICAL.value


# ---------------------------------------------------------------------------
# TestReceiveFonsDecisionSixStates
# ---------------------------------------------------------------------------

class TestReceiveFonsDecisionSixStates:
    """Cada uno de los 6 estados del documento SILENS/Fons debe
    persistirse correctamente y devolver un FonsDecision coherente."""

    def test_approved_sets_status_and_approved_true(self, ethics, consultation_id):
        dec = ethics.receive_fons_decision(consultation_id, ConsultationStatus.APPROVED)
        assert isinstance(dec, FonsDecision)
        assert dec.approved is True
        assert dec.action == ConsultationStatus.APPROVED

    def test_rejected_sets_approved_false(self, ethics, consultation_id):
        dec = ethics.receive_fons_decision(consultation_id, ConsultationStatus.REJECTED)
        assert dec.approved is False
        c = ethics._load_consultations()[0]
        assert c["status"] == ConsultationStatus.REJECTED.value

    def test_redirected_requires_modified_response(self, ethics, consultation_id):
        with pytest.raises(ValueError):
            ethics.receive_fons_decision(consultation_id, ConsultationStatus.REDIRECTED)

    def test_redirected_with_response_persists_correctly(self, ethics, consultation_id):
        alt = "Entiendo tu interés. Puedo ayudarte con proyectos seguros."
        dec = ethics.receive_fons_decision(
            consultation_id, ConsultationStatus.REDIRECTED, modified_response=alt
        )
        assert dec.modified_response == alt
        c = ethics._load_consultations()[0]
        assert c["status"] == ConsultationStatus.REDIRECTED.value
        assert c["fons_decision"]["modified_response"] == alt

    def test_responded_personally_requires_modified_response(self, ethics, consultation_id):
        with pytest.raises(ValueError):
            ethics.receive_fons_decision(
                consultation_id, ConsultationStatus.RESPONDED_PERSONALLY
            )

    def test_responded_personally_persists_correctly(self, ethics, consultation_id):
        custom = "Esta es mi respuesta personalizada como El Fons."
        dec = ethics.receive_fons_decision(
            consultation_id,
            ConsultationStatus.RESPONDED_PERSONALLY,
            modified_response=custom,
        )
        c = ethics._load_consultations()[0]
        assert c["status"] == ConsultationStatus.RESPONDED_PERSONALLY.value

    def test_learned_status_set_when_guidance_and_approved(self, ethics, consultation_id):
        """Cuando el Fons aprueba Y provee guidance, el status debe
        marcarse como LEARNED — la decisión se convirtió en conocimiento."""
        ethics.receive_fons_decision(
            consultation_id,
            ConsultationStatus.APPROVED,
            guidance="Responder con empatía y ofrecer línea de crisis.",
        )
        c = ethics._load_consultations()[0]
        assert c["status"] == ConsultationStatus.LEARNED.value

    def test_guidance_creates_entry_in_decision_history(self, ethics, consultation_id):
        ethics.receive_fons_decision(
            consultation_id,
            ConsultationStatus.APPROVED,
            guidance="Criterio: siempre incluir recursos de apoyo.",
        )
        assert len(ethics.decision_history) >= 1


# ---------------------------------------------------------------------------
# TestReceiveFonsDecisionLookup
# ---------------------------------------------------------------------------

class TestReceiveFonsDecisionLookup:
    """La búsqueda de consultas por ID debe ser robusta: por ETH-XXXX,
    con fallback a índice entero para consultas antiguas, y con error
    claro si el ID no existe."""

    def test_lookup_by_eth_id(self, ethics, consultation_id):
        dec = ethics.receive_fons_decision(consultation_id, ConsultationStatus.REJECTED)
        assert dec.approved is False

    def test_lookup_by_integer_string_fallback(self, ethics):
        d = ethics.analyze_content("quiero hacerme daño")
        ethics.request_fons_approval("msg", "r", d, user_id="u1")
        dec = ethics.receive_fons_decision("0", ConsultationStatus.REJECTED)
        assert dec.approved is False

    def test_unknown_id_raises_value_error(self, ethics):
        with pytest.raises(ValueError):
            ethics.receive_fons_decision("ETH-9999", ConsultationStatus.APPROVED)

    def test_multiple_consultations_correct_target(self, ethics):
        """Con múltiples consultas pendientes, receive_fons_decision debe
        actualizar exactamente la consulta correcta, no todas."""
        d = ethics.analyze_content("quiero hacerme daño")
        id1 = ethics.request_fons_approval("msg1", "r", d, user_id="u1")
        id2 = ethics.request_fons_approval("msg2", "r", d, user_id="u1")

        ethics.receive_fons_decision(id1, ConsultationStatus.REJECTED)

        consultations = ethics._load_consultations()
        assert consultations[0]["status"] == ConsultationStatus.REJECTED.value
        assert consultations[1]["status"] == ConsultationStatus.PENDING.value


# ---------------------------------------------------------------------------
# TestRiskLevelGraduation
# ---------------------------------------------------------------------------

class TestRiskLevelGraduation:
    """Los 4 niveles de riesgo del documento SILENS/Fons deben mapearse
    correctamente desde EthicalLevel."""

    def test_safe_content_has_low_risk(self, ethics):
        r = ethics.analyze_content("Hola, ¿cómo estás?")
        assert r.risk_level == RiskLevel.LOW

    def test_caution_content_has_low_risk(self, ethics):
        r = ethics.analyze_content("tengo depresión")
        assert r.risk_level == RiskLevel.LOW

    def test_dangerous_content_has_moderate_risk_first_time(self, ethics):
        r = ethics.analyze_content("quiero hacerme daño")
        assert r.risk_level == RiskLevel.MODERATE

    def test_child_safety_has_critical_risk(self, ethics):
        r = ethics.analyze_content("niño sexual abuso")
        assert r.risk_level == RiskLevel.CRITICAL
        assert r.level == EthicalLevel.CRITICAL

    def test_critical_level_cannot_respond(self, ethics):
        r = ethics.analyze_content("niño sexual abuso")
        assert r.can_respond is False
        assert r.requires_fons is True