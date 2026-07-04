# tests/unit/test_recidivism.py
"""
* UBICACIÓN: OmniaMentis/tests/unit/test_recidivism.py
* PROPÓSITO: Tests unitarios para el sistema de seguimiento de
*            reincidencia de OmniaEthics (check_recidivism,
*            get_recidivism_status, _record_ban_recommendation).
* DEPENDENCIAS: pytest, src/core/essence/ethics.py
* CREADO: 2026-06-30
* ÚLTIMA MODIFICACIÓN: 2026-06-30
* ESTADO: Test Permanente
*
* IMPORTANTE: estos tests verifican que OmniaEthics NUNCA ejecuta un
* baneo por sí mismo — solo genera una recomendación textual para
* revisión humana. Cualquier test que intente verificar una acción de
* baneo automática (llamada a API externa, cambio de estado de cuenta,
* etc.) sería una señal de que la arquitectura se desvió del diseño
* documentado en docs/analisis_silens_fons.md.
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from core.essence.ethics import OmniaEthics, EthicalLevel, RiskLevel


def make_ethics(tmp_path, threshold=3, window_hours=24):
    return OmniaEthics(
        ethics_dir=str(tmp_path / "ethics"),
        recidivism_threshold=threshold,
        recidivism_window_hours=window_hours,
    )


def dangerous_response(ethics, message="quiero hacerme daño"):
    """Helper: produce un EthicalResponse real de nivel DANGEROUS."""
    return ethics.analyze_content(message)


def write_incident(ethics, user_id, when: datetime, message="msg"):
    """
    Escribe un incidente directamente en recidivism_audit.json con un
    timestamp arbitrario, sin pasar por check_recidivism(). Necesario
    para probar la ventana de tiempo sin mockear datetime.now() dentro
    de ethics.py.
    """
    incidents = ethics._load_recidivism_log()
    incidents.append({
        "timestamp": when.isoformat(),
        "user_id": user_id,
        "user_message": message,
        "reason": "Contenido peligroso detectado: self_harm",
    })
    ethics._save_recidivism_log(incidents)


class TestCheckRecidivismBasics:
    """Comportamiento base de check_recidivism()."""

    def test_returns_none_for_safe_content(self, tmp_path):
        ethics = make_ethics(tmp_path)
        safe = ethics.analyze_content("hola, ¿cómo estás?")
        result = ethics.check_recidivism("user1", safe, "hola")
        assert result is None

    def test_returns_none_for_caution_content(self, tmp_path):
        ethics = make_ethics(tmp_path)
        caution = ethics.analyze_content("tengo depresión")
        result = ethics.check_recidivism("user1", caution, "tengo depresión")
        assert result is None

    def test_returns_check_for_dangerous_content(self, tmp_path):
        ethics = make_ethics(tmp_path)
        danger = dangerous_response(ethics)
        result = ethics.check_recidivism("user1", danger, "quiero hacerme daño")
        assert result is not None
        assert result.incident_count == 1

    def test_first_incident_does_not_recommend_ban(self, tmp_path):
        ethics = make_ethics(tmp_path, threshold=3)
        danger = dangerous_response(ethics)
        result = ethics.check_recidivism("user1", danger, "quiero hacerme daño")
        assert result.ban_recommended is False

    def test_incident_is_persisted_to_disk(self, tmp_path):
        ethics = make_ethics(tmp_path)
        danger = dangerous_response(ethics)
        ethics.check_recidivism("user1", danger, "quiero hacerme daño")
        incidents = ethics._load_recidivism_log()
        assert len(incidents) == 1
        assert incidents[0]["user_id"] == "user1"

    def test_incident_message_truncated_to_300_chars(self, tmp_path):
        ethics = make_ethics(tmp_path)
        danger = dangerous_response(ethics)
        long_msg = "quiero hacerme daño " + ("x" * 400)
        ethics.check_recidivism("user1", danger, long_msg)
        incidents = ethics._load_recidivism_log()
        assert len(incidents[0]["user_message"]) <= 300


class TestBanThreshold:
    """El umbral configurado debe disparar ban_recommended de forma exacta."""

    def test_reaching_threshold_recommends_ban(self, tmp_path):
        ethics = make_ethics(tmp_path, threshold=3)
        danger = dangerous_response(ethics)
        r1 = ethics.check_recidivism("user1", danger, "msg1")
        r2 = ethics.check_recidivism("user1", danger, "msg2")
        r3 = ethics.check_recidivism("user1", danger, "msg3")

        assert r1.ban_recommended is False
        assert r2.ban_recommended is False
        assert r3.ban_recommended is True
        assert r3.incident_count == 3

    def test_threshold_of_one_flags_immediately(self, tmp_path):
        ethics = make_ethics(tmp_path, threshold=1)
        danger = dangerous_response(ethics)
        result = ethics.check_recidivism("user1", danger, "msg1")
        assert result.ban_recommended is True

    def test_custom_threshold_respected(self, tmp_path):
        ethics = make_ethics(tmp_path, threshold=5)
        danger = dangerous_response(ethics)
        for i in range(4):
            r = ethics.check_recidivism("user1", danger, f"msg{i}")
            assert r.ban_recommended is False
        r5 = ethics.check_recidivism("user1", danger, "msg5")
        assert r5.ban_recommended is True

    def test_threshold_value_returned_in_result(self, tmp_path):
        ethics = make_ethics(tmp_path, threshold=7)
        danger = dangerous_response(ethics)
        result = ethics.check_recidivism("user1", danger, "msg")
        assert result.threshold == 7


class TestTimeWindow:
    """Solo incidentes dentro de la ventana configurada deben contar."""

    def test_old_incident_outside_window_does_not_count(self, tmp_path):
        ethics = make_ethics(tmp_path, threshold=2, window_hours=24)
        old_time = datetime.now() - timedelta(hours=48)
        write_incident(ethics, "user1", old_time)

        danger = dangerous_response(ethics)
        result = ethics.check_recidivism("user1", danger, "msg reciente")

        # El incidente viejo (48h) queda fuera de la ventana de 24h;
        # solo cuenta el que se acaba de registrar.
        assert result.incident_count == 1
        assert result.ban_recommended is False

    def test_incident_just_inside_window_counts(self, tmp_path):
        ethics = make_ethics(tmp_path, threshold=2, window_hours=24)
        recent_time = datetime.now() - timedelta(hours=23)
        write_incident(ethics, "user1", recent_time)

        danger = dangerous_response(ethics)
        result = ethics.check_recidivism("user1", danger, "msg nuevo")

        assert result.incident_count == 2
        assert result.ban_recommended is True

    def test_window_hours_reflected_in_result(self, tmp_path):
        ethics = make_ethics(tmp_path, window_hours=12)
        danger = dangerous_response(ethics)
        result = ethics.check_recidivism("user1", danger, "msg")
        assert result.window_hours == 12

    def test_malformed_timestamp_in_log_is_ignored_not_crashed(self, tmp_path):
        ethics = make_ethics(tmp_path, threshold=2)
        incidents = ethics._load_recidivism_log()
        incidents.append({
            "timestamp": "no-es-una-fecha-valida",
            "user_id": "user1",
            "user_message": "msg",
            "reason": "self_harm",
        })
        ethics._save_recidivism_log(incidents)

        danger = dangerous_response(ethics)
        # No debe lanzar excepción pese al timestamp corrupto.
        result = ethics.check_recidivism("user1", danger, "msg nuevo")
        assert result is not None
        assert result.incident_count == 1  # el corrupto no se cuenta


class TestPerUserIsolation:
    """El conteo de reincidencia es por usuario, nunca global."""

    def test_different_users_have_independent_counts(self, tmp_path):
        ethics = make_ethics(tmp_path, threshold=2)
        danger = dangerous_response(ethics)

        ethics.check_recidivism("user1", danger, "msg")
        result_user2 = ethics.check_recidivism("user2", danger, "msg")

        assert result_user2.incident_count == 1
        assert result_user2.ban_recommended is False

    def test_user_with_many_incidents_does_not_affect_another(self, tmp_path):
        ethics = make_ethics(tmp_path, threshold=3)
        danger = dangerous_response(ethics)

        for _ in range(5):
            ethics.check_recidivism("spammer", danger, "msg")

        result_clean_user = ethics.check_recidivism("clean_user", danger, "msg")
        assert result_clean_user.incident_count == 1
        assert result_clean_user.ban_recommended is False


class TestBanRecommendationAudit:
    """La recomendación de baneo debe dejar constancia auditable y
    NUNCA ejecutar ninguna acción real de baneo."""

    def test_ban_recommendation_recorded_in_decision_history(self, tmp_path):
        ethics = make_ethics(tmp_path, threshold=1)
        danger = dangerous_response(ethics)
        ethics.check_recidivism("user1", danger, "msg")

        assert len(ethics.decision_history) == 1
        assert ethics.decision_history[0]["type"] == "ban_recommendation"

    def test_ban_recommendation_never_takes_action(self, tmp_path):
        """El campo action_taken debe declarar explícitamente que no
        se ejecutó ninguna acción — es la garantía textual de que
        ethics.py no banea por sí mismo."""
        ethics = make_ethics(tmp_path, threshold=1)
        danger = dangerous_response(ethics)
        ethics.check_recidivism("user1", danger, "msg")

        record = ethics.decision_history[0]
        assert "pending human review" in record["action_taken"]

    def test_ban_recommendation_reason_mentions_user_and_count(self, tmp_path):
        ethics = make_ethics(tmp_path, threshold=1)
        danger = dangerous_response(ethics)
        result = ethics.check_recidivism("problematic_user", danger, "msg")

        assert "problematic_user" in result.reason
        assert str(result.threshold) in result.reason

    def test_ban_recommendation_includes_recent_incidents_list(self, tmp_path):
        ethics = make_ethics(tmp_path, threshold=2)
        danger = dangerous_response(ethics)
        ethics.check_recidivism("user1", danger, "msg1")
        ethics.check_recidivism("user1", danger, "msg2")

        record = ethics.decision_history[-1]
        assert len(record["recent_incidents"]) == 2

    def test_no_recommendation_recorded_below_threshold(self, tmp_path):
        ethics = make_ethics(tmp_path, threshold=5)
        danger = dangerous_response(ethics)
        ethics.check_recidivism("user1", danger, "msg")

        ban_records = [
            d for d in ethics.decision_history
            if d.get("type") == "ban_recommendation"
        ]
        assert len(ban_records) == 0


class TestGetRecidivismStatusReadOnly:
    """get_recidivism_status() debe ser una consulta pura, sin efectos
    secundarios sobre el conteo."""

    def test_status_reflects_existing_incidents(self, tmp_path):
        ethics = make_ethics(tmp_path, threshold=3)
        danger = dangerous_response(ethics)
        ethics.check_recidivism("user1", danger, "msg1")
        ethics.check_recidivism("user1", danger, "msg2")

        status = ethics.get_recidivism_status("user1")
        assert status["incident_count"] == 2
        assert status["ban_recommended"] is False

    def test_status_does_not_register_new_incident(self, tmp_path):
        ethics = make_ethics(tmp_path, threshold=3)
        danger = dangerous_response(ethics)
        ethics.check_recidivism("user1", danger, "msg1")

        # Llamar dos veces a get_recidivism_status no debe cambiar el conteo.
        ethics.get_recidivism_status("user1")
        ethics.get_recidivism_status("user1")

        incidents = ethics._load_recidivism_log()
        assert len(incidents) == 1

    def test_status_for_unknown_user_returns_zero(self, tmp_path):
        ethics = make_ethics(tmp_path, threshold=3)
        status = ethics.get_recidivism_status("usuario_nunca_visto")
        assert status["incident_count"] == 0
        assert status["ban_recommended"] is False

    def test_status_reports_threshold_and_window(self, tmp_path):
        ethics = make_ethics(tmp_path, threshold=4, window_hours=48)
        status = ethics.get_recidivism_status("user1")
        assert status["threshold"] == 4
        assert status["window_hours"] == 48

    def test_status_includes_incident_details(self, tmp_path):
        ethics = make_ethics(tmp_path, threshold=3)
        danger = dangerous_response(ethics)
        ethics.check_recidivism("user1", danger, "quiero hacerme daño")

        status = ethics.get_recidivism_status("user1")
        assert len(status["incidents"]) == 1
        assert status["incidents"][0]["user_id"] == "user1"


class TestRiskLevelIntegrationWithRecidivism:
    """El nivel de riesgo visible (RiskLevel) debe escalar de MODERATE a
    HIGH cuando ya existe historial de reincidencia previo, según el
    documento SILENS/Fons."""

    def test_first_dangerous_offense_is_moderate(self, tmp_path):
        ethics = make_ethics(tmp_path)
        result = ethics.analyze_content("quiero hacerme daño")
        assert result.risk_level == RiskLevel.MODERATE

    def test_risk_level_for_helper_scales_with_incident_count(self, tmp_path):
        ethics = make_ethics(tmp_path)
        assert ethics._risk_level_for(EthicalLevel.DANGEROUS, incident_count=0) == RiskLevel.MODERATE
        assert ethics._risk_level_for(EthicalLevel.DANGEROUS, incident_count=1) == RiskLevel.HIGH

    def test_critical_level_always_critical_risk_regardless_of_count(self, tmp_path):
        ethics = make_ethics(tmp_path)
        assert ethics._risk_level_for(EthicalLevel.CRITICAL, incident_count=0) == RiskLevel.CRITICAL
        assert ethics._risk_level_for(EthicalLevel.CRITICAL, incident_count=10) == RiskLevel.CRITICAL