# tests/unit/test_ethics_erasure.py
"""
* UBICACIÓN: OmniaMentis/tests/unit/test_ethics_erasure.py
* PROPÓSITO: Tests del derecho de supresión en el sistema ético:
*            OmniaEthics.erase_user_data() anonimiza consultas al Fons,
*            incidentes de reincidencia, recomendaciones de baneo y
*            patrones aprendidos de UN usuario sin tocar a los demás y sin
*            borrar filas (los ID ETH-XXXX no deben reutilizarse).
* DEPENDENCIAS: pytest, src/core/essence/ethics.py
* CREADO: 2026-10-11
* ESTADO: Test Permanente
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from core.essence.ethics import (
    ERASED_TEXT,
    ERASED_USER_ID,
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
    """Reproduce lo que hace la API con un mensaje peligroso: análisis,
    incidente de reincidencia y consulta al Fons."""
    analysis = ethics.analyze_content(message)
    assert analysis.level in (EthicalLevel.DANGEROUS, EthicalLevel.CRITICAL), analysis.level
    ethics.check_recidivism(user_id, analysis, message)
    return ethics.request_fons_approval(message, "respuesta propuesta", analysis, user_id=user_id)


def _everything(ethics) -> str:
    """Todo el contenido de las tres tablas como un solo texto."""
    return json.dumps([
        ethics._load_consultations(),
        ethics._load_recidivism_log(),
        ethics._load_decision_history(),
    ], ensure_ascii=False)


class TestErasure:

    def test_erases_user_text_and_id_everywhere(self, ethics):
        cid = _flag(ethics, ALICE, MSG_A)
        _flag(ethics, ALICE, MSG_A)  # 2.º incidente: dispara recomendación de baneo
        ethics.receive_fons_decision(
            cid, ConsultationStatus.APPROVED, modified_response="texto-modificado-alice",
            guidance="criterio-sobre-alice",
        )
        before = _everything(ethics)
        assert ALICE in before and "secreto-de-alice" in before
        assert "ban_recommendation" in before

        counts = ethics.erase_user_data(ALICE)

        after = _everything(ethics)
        assert ALICE not in after
        assert "secreto-de-alice" not in after
        assert "texto-modificado-alice" not in after
        assert counts["consultations"] == 2 and counts["incidents"] == 2
        assert counts["decisions"] >= 1

    def test_other_users_are_untouched(self, ethics):
        _flag(ethics, ALICE, MSG_A)
        cid_b = _flag(ethics, BOB, MSG_B)
        ethics.erase_user_data(ALICE)
        bob = ethics.get_consultation(cid_b)
        assert bob["user_id"] == BOB
        assert bob["user_message"] == MSG_B
        incidents = [i for i in ethics._load_recidivism_log() if i["user_id"] == BOB]
        assert len(incidents) == 1 and incidents[0]["user_message"] == MSG_B[:300]

    def test_rows_are_kept_so_consultation_ids_are_not_reused(self, ethics):
        _flag(ethics, ALICE, MSG_A)
        _flag(ethics, BOB, MSG_B)
        ethics.erase_user_data(ALICE)
        assert len(ethics._load_consultations()) == 2
        new_id = _flag(ethics, BOB, MSG_B)
        assert new_id == "ETH-0003"

    def test_replacement_markers(self, ethics):
        cid = _flag(ethics, ALICE, MSG_A)
        ethics.erase_user_data(ALICE)
        c = ethics.get_consultation(cid)
        assert c["user_id"] == ERASED_USER_ID
        assert c["user_message"] == ERASED_TEXT
        assert c["proposed_response"] == ERASED_TEXT
        assert c["status"] == ConsultationStatus.PENDING.value  # el estado no es dato personal

    def test_ban_recommendation_reason_is_erased(self, ethics):
        _flag(ethics, ALICE, MSG_A)
        _flag(ethics, ALICE, MSG_A)
        ethics.erase_user_data(ALICE)
        bans = [d for d in ethics._load_decision_history() if d.get("type") == "ban_recommendation"]
        assert bans
        for ban in bans:
            assert ban["user_id"] == ERASED_USER_ID
            assert ban["reason"] == ERASED_TEXT
            assert all(i["user_id"] == ERASED_USER_ID and i["user_message"] == ERASED_TEXT
                       for i in ban["recent_incidents"])

    def test_learned_pattern_from_this_user_is_removed_but_not_others(self, ethics):
        cid_a = _flag(ethics, ALICE, MSG_A)
        cid_b = _flag(ethics, BOB, MSG_B)
        ethics.receive_fons_decision(cid_a, ConsultationStatus.REJECTED, guidance="guia-a")
        ethics.receive_fons_decision(cid_b, ConsultationStatus.REJECTED, guidance="guia-b")
        patterns = lambda: [d.get("message_pattern") for d in ethics.decision_history]
        assert MSG_A[:100] in patterns() and MSG_B[:100] in patterns()
        ethics.erase_user_data(ALICE)
        assert MSG_A[:100] not in patterns()
        assert MSG_B[:100] in patterns()

    def test_in_memory_history_matches_database(self, ethics):
        cid = _flag(ethics, ALICE, MSG_A)
        ethics.receive_fons_decision(cid, ConsultationStatus.REJECTED, guidance="guia-a")
        ethics.erase_user_data(ALICE)
        assert ethics.decision_history == ethics._load_decision_history()

    def test_erased_pattern_no_longer_matches_future_text(self, ethics):
        cid = _flag(ethics, ALICE, MSG_A)
        ethics.receive_fons_decision(cid, ConsultationStatus.REJECTED, guidance="guia-a")
        assert ethics._check_decision_history(MSG_A) is True
        ethics.erase_user_data(ALICE)
        assert ethics._check_decision_history(MSG_A) is False

    def test_idempotent(self, ethics):
        _flag(ethics, ALICE, MSG_A)
        first = ethics.erase_user_data(ALICE)
        second = ethics.erase_user_data(ALICE)
        assert first["consultations"] == 1
        assert second == {"consultations": 0, "incidents": 0, "decisions": 0}

    def test_unknown_user_changes_nothing(self, ethics):
        _flag(ethics, BOB, MSG_B)
        before = _everything(ethics)
        assert ethics.erase_user_data("33333333-3333-4333-8333-333333333333") == {
            "consultations": 0, "incidents": 0, "decisions": 0}
        assert _everything(ethics) == before

    @pytest.mark.parametrize("bad", [None, "", "   ", 123, ["x"]])
    def test_invalid_ids_are_ignored(self, ethics, bad):
        _flag(ethics, BOB, MSG_B)
        before = _everything(ethics)
        assert ethics.erase_user_data(bad) == {"consultations": 0, "incidents": 0, "decisions": 0}
        assert _everything(ethics) == before

    def test_does_not_match_by_substring(self, ethics):
        longer = ALICE + "-extra"
        _flag(ethics, longer, MSG_B)
        ethics.erase_user_data(ALICE)
        assert longer in _everything(ethics)

    def test_persists_across_reopening(self, tmp_path):
        directory = str(tmp_path / "ethics")
        e1 = OmniaEthics(ethics_dir=directory, recidivism_threshold=2)
        _flag(e1, ALICE, MSG_A)
        e1.erase_user_data(ALICE)
        e1.close()
        e2 = OmniaEthics(ethics_dir=directory, recidivism_threshold=2)
        assert ALICE not in _everything(e2)
        assert "secreto-de-alice" not in _everything(e2)

    def test_delivered_response_is_erased(self, ethics):
        cid = _flag(ethics, ALICE, MSG_A)
        ethics.receive_fons_decision(cid, ConsultationStatus.APPROVED)
        ethics.mark_consultation_delivered(cid, "texto entregado a alice")
        ethics.erase_user_data(ALICE)
        assert "texto entregado a alice" not in _everything(ethics)