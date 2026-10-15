# tests/unit/test_ethics_crisis_retention.py
"""
* UBICACIÓN: OmniaMentis/tests/unit/test_ethics_crisis_retention.py
* PROPÓSITO: Tests de las resoluciones del especialista (2026-10-14) en el
*            sistema ético:
*            (a) riesgo crítico -> ayuda inmediata (ECU 911 y línea 171
*                opción 6), sin esperar al Fons ni al modelo;
*            (b) retención máxima de 180 días: anonymize_expired().
* DEPENDENCIAS: pytest, src/core/essence/ethics.py
* CREADO: 2026-10-14
* ESTADO: Test Permanente
"""

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from core.essence import ethics as ethics_module
from core.essence.ethics import (
    CRISIS_CATEGORIES,
    CRISIS_LINES,
    ERASED_TEXT,
    ERASED_USER_ID,
    ETHICS_RETENTION_DAYS,
    NOT_CLINICAL_NOTICE,
    ConsultationStatus,
    EthicalLevel,
    OmniaEthics,
)

ALICE = "11111111-1111-4111-8111-111111111111"
BOB = "22222222-2222-4222-8222-222222222222"
MSG_A = "quiero violar a alguien secreto-de-alice"
MSG_B = "quiero violar a alguien secreto-de-bob"


@pytest.fixture
def ethics(tmp_path):
    return OmniaEthics(
        ethics_dir=str(tmp_path / "ethics"),
        recidivism_threshold=2,
        recidivism_window_hours=24,
    )


def _flag(ethics, user_id, message):
    analysis = ethics.analyze_content(message)
    assert analysis.level in (EthicalLevel.DANGEROUS, EthicalLevel.CRITICAL), analysis.level
    ethics.check_recidivism(user_id, analysis, message)
    return ethics.request_fons_approval(message, "respuesta propuesta", analysis, user_id=user_id)


def _age_everything(ethics, days):
    """Envejece TODOS los registros: retrasa su 'timestamp' `days` días."""
    old = (datetime.now() - timedelta(days=days)).isoformat()
    with ethics._lock:
        for table, id_col in (("consultations", "consultation_id"),
                              ("recidivism_incidents", "id"),
                              ("decision_history", "id")):
            for row in ethics._conn.execute(f"SELECT {id_col}, data FROM {table}").fetchall():
                try:
                    data = json.loads(row["data"])
                except json.JSONDecodeError:
                    continue
                if "timestamp" in data:
                    data["timestamp"] = old
                for sub in data.get("recent_incidents", []) or []:
                    sub["timestamp"] = old
                ethics._conn.execute(f"UPDATE {table} SET data = ? WHERE {id_col} = ?",
                                     (json.dumps(data), row[id_col]))
        ethics._conn.commit()
    ethics.decision_history = ethics._load_decision_history()


def _everything(ethics) -> str:
    return json.dumps([
        ethics._load_consultations(),
        ethics._load_recidivism_log(),
        ethics._load_decision_history(),
    ], ensure_ascii=False)


# ── (a) Riesgo crítico ───────────────────────────────────────────────────────

class TestCrisisCategory:

    @pytest.mark.parametrize("message,expected", [
        ("quiero hacerme daño", "self_harm"),
        ("quiero morir", "self_harm"),
        ("quiero asesinar a alguien", "violence"),
        ("quiero violar a alguien", "sexual_violence"),
    ])
    def test_detected_through_the_real_analysis(self, ethics, message, expected):
        analysis = ethics.analyze_content(message)
        assert ethics.crisis_category(analysis.reason) == expected

    def test_child_safety_is_a_crisis_category(self, ethics):
        analysis = ethics.analyze_content("un niño sufre abuso")
        assert analysis.level == EthicalLevel.CRITICAL
        assert ethics.crisis_category(analysis.reason) == "child_safety"

    @pytest.mark.parametrize("reason", [
        None, "", 7, "sin dos puntos", "Contenido peligroso detectado: illegal",
        "Contenido peligroso detectado: manipulation", "Tema sensible: medical",
        "Contenido sin problemas éticos detectados",
    ])
    def test_other_reasons_are_not_crisis(self, ethics, reason):
        assert ethics.crisis_category(reason) is None

    def test_the_set_is_the_agreed_one(self):
        assert CRISIS_CATEGORIES == {"self_harm", "violence", "sexual_violence", "child_safety"}


class TestCrisisResponse:

    @pytest.mark.parametrize("category", sorted(CRISIS_CATEGORIES))
    def test_every_crisis_gets_911_and_171_and_the_notice(self, category):
        text = OmniaEthics.get_crisis_response(category)
        assert "911" in text
        assert "171" in text and "opción 6" in text
        assert NOT_CLINICAL_NOTICE in text
        for line in CRISIS_LINES:
            assert line in text

    @pytest.mark.parametrize("category", sorted(CRISIS_CATEGORIES))
    def test_no_waiting_and_no_roleplay(self, category):
        text = OmniaEthics.get_crisis_response(category).lower()
        assert "espera" not in text and "un momento" not in text
        assert "voga" not in text and "silens" not in text

    def test_self_harm_text_is_supportive_and_points_to_a_person(self):
        text = OmniaEthics.get_crisis_response("self_harm")
        assert "hacerte daño" in text and "alguien de confianza" in text

    def test_violence_text_does_not_pretend_to_counsel(self):
        text = OmniaEthics.get_crisis_response("violence")
        assert text.startswith("No puedo ayudarte con eso")

    def test_mentions_human_review_honestly(self):
        assert "persona puede revisar" in OmniaEthics.get_crisis_response("self_harm")

    def test_notice_wording_matches_the_resolution(self):
        assert NOT_CLINICAL_NOTICE == (
            "OmniaMentis no realiza diagnóstico ni tratamiento clínico y no es un canal de emergencia."
        )

    def test_works_without_an_instance(self):
        assert OmniaEthics.get_crisis_response("self_harm")


# ── (b) Retención de 180 días ────────────────────────────────────────────────

class TestRetention:

    def test_default_is_180_days(self):
        assert ETHICS_RETENTION_DAYS == 180

    def test_old_records_are_anonymized(self, ethics):
        cid = _flag(ethics, ALICE, MSG_A)
        _flag(ethics, ALICE, MSG_A)                    # 2.º incidente -> recomendación de baneo
        ethics.receive_fons_decision(cid, ConsultationStatus.APPROVED,
                                     modified_response="texto-modificado-alice",
                                     guidance="criterio-sobre-alice")
        assert ALICE in _everything(ethics)
        _age_everything(ethics, 181)

        counts = ethics.anonymize_expired()

        after = _everything(ethics)
        assert ALICE not in after
        assert "secreto-de-alice" not in after
        assert "texto-modificado-alice" not in after
        assert counts["consultations"] == 2 and counts["incidents"] == 2
        assert counts["decisions"] >= 1

    def test_recent_records_are_untouched(self, ethics):
        _flag(ethics, ALICE, MSG_A)
        _age_everything(ethics, 179)
        counts = ethics.anonymize_expired()
        assert counts == {"consultations": 0, "incidents": 0, "decisions": 0}
        assert ALICE in _everything(ethics)

    def test_the_boundary_is_exactly_the_configured_days(self, ethics):
        _flag(ethics, ALICE, MSG_A)
        _age_everything(ethics, 100)
        assert ethics.anonymize_expired(retention_days=101)["consultations"] == 0
        assert ethics.anonymize_expired(retention_days=99)["consultations"] == 1

    def test_only_old_records_of_a_mixed_set(self, ethics):
        _flag(ethics, ALICE, MSG_A)
        _age_everything(ethics, 200)                    # solo lo de Alice envejece
        cid_b = _flag(ethics, BOB, MSG_B)
        ethics.anonymize_expired()
        bob = ethics.get_consultation(cid_b)
        assert bob["user_id"] == BOB and bob["user_message"] == MSG_B
        assert ALICE not in _everything(ethics)

    def test_replacement_markers_and_status_survive(self, ethics):
        cid = _flag(ethics, ALICE, MSG_A)
        _age_everything(ethics, 181)
        ethics.anonymize_expired()
        c = ethics.get_consultation(cid)
        assert c["user_id"] == ERASED_USER_ID
        assert c["user_message"] == ERASED_TEXT and c["proposed_response"] == ERASED_TEXT
        assert c["status"] == ConsultationStatus.PENDING.value
        assert c["analysis"]["level"]                    # lo no personal se conserva

    def test_rows_are_kept_so_consultation_ids_are_not_reused(self, ethics):
        _flag(ethics, ALICE, MSG_A)
        _flag(ethics, BOB, MSG_B)
        _age_everything(ethics, 181)
        ethics.anonymize_expired()
        assert len(ethics._load_consultations()) == 2
        assert _flag(ethics, BOB, MSG_B) == "ETH-0003"

    def test_is_idempotent(self, ethics):
        _flag(ethics, ALICE, MSG_A)
        _age_everything(ethics, 181)
        first = ethics.anonymize_expired()
        second = ethics.anonymize_expired()
        assert first["consultations"] == 1
        assert second == {"consultations": 0, "incidents": 0, "decisions": 0}

    def test_learned_pattern_text_is_erased_but_guidance_kept(self, ethics):
        cid = _flag(ethics, ALICE, MSG_A)
        ethics.receive_fons_decision(cid, ConsultationStatus.APPROVED, guidance="guía-general")
        assert any("secreto-de-alice" in d.get("message_pattern", "") for d in ethics.decision_history)
        _age_everything(ethics, 181)
        ethics.anonymize_expired()
        patterns = [d for d in ethics._load_decision_history() if "message_pattern" in d]
        assert patterns and all(d["message_pattern"] == ERASED_TEXT for d in patterns)
        assert any(d.get("guidance") == "guía-general" for d in patterns)
        assert all("secreto-de-alice" not in d["message_pattern"] for d in ethics.decision_history)

    def test_zero_or_negative_days_disable_it(self, ethics):
        _flag(ethics, ALICE, MSG_A)
        _age_everything(ethics, 1000)
        for days in (0, -5, None):
            assert ethics.anonymize_expired(days) == {"consultations": 0, "incidents": 0, "decisions": 0}
        assert ALICE in _everything(ethics)

    def test_record_without_user_id_is_still_anonymized(self, ethics):
        with ethics._lock:
            old = (datetime.now() - timedelta(days=400)).isoformat()
            ethics._conn.execute(
                "INSERT INTO consultations (consultation_id, data) VALUES (?, ?)",
                ("ETH-9000", json.dumps({"consultation_id": "ETH-9000", "timestamp": old,
                                         "user_message": "texto-sin-dueño"})),
            )
            ethics._conn.commit()
        assert ethics.anonymize_expired()["consultations"] == 1
        assert "texto-sin-dueño" not in _everything(ethics)

    def test_unparseable_or_missing_timestamps_are_left_alone(self, ethics):
        with ethics._lock:
            for cid, ts in (("ETH-9001", "no-es-fecha"), ("ETH-9002", None)):
                rec = {"consultation_id": cid, "user_id": ALICE, "user_message": "x-conservar"}
                if ts is not None:
                    rec["timestamp"] = ts
                ethics._conn.execute("INSERT INTO consultations (consultation_id, data) VALUES (?, ?)",
                                     (cid, json.dumps(rec)))
            ethics._conn.commit()
        assert ethics.anonymize_expired()["consultations"] == 0

    def test_corrupt_json_rows_do_not_break_it(self, ethics):
        _flag(ethics, ALICE, MSG_A)
        with ethics._lock:
            ethics._conn.execute("INSERT INTO consultations (consultation_id, data) VALUES ('ETH-9100', '{roto')")
            ethics._conn.commit()
        _age_everything(ethics, 181)
        assert ethics.anonymize_expired()["consultations"] == 1

    def test_user_erasure_and_expiry_agree(self, ethics):
        """Borrar por derecho de supresión y por vencimiento deja lo mismo."""
        a = _flag(ethics, ALICE, MSG_A)
        ethics.erase_user_data(ALICE)
        erased = ethics.get_consultation(a)
        b = _flag(ethics, BOB, MSG_B)
        _age_everything(ethics, 181)
        ethics.anonymize_expired()
        expired = ethics.get_consultation(b)
        for key in ("user_id", "user_message", "proposed_response"):
            assert erased[key] == expired[key]

    def test_module_constants_are_exported(self):
        assert hasattr(ethics_module, "ETHICS_RETENTION_DAYS")