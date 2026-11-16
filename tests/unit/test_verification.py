"""Pruebas de core/verification/verification.py (Corporal solo adultos; retención mínima)."""
import os
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from core.verification.verification import (CONSENT_TEXT_VERSION, MAX_IMAGE_BYTES, VerificationError,
                                            VerificationStore, age_on, sniff_image)

JPG = b"\xff\xd8\xff\xe0" + b"0" * 50
PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 50
WEBP = b"RIFF\x00\x00\x00\x00WEBP" + b"0" * 20
T0 = datetime(2026, 11, 15, 12, 0, tzinfo=timezone.utc)
ADULT_IMGS = {"id_doc": JPG, "face": PNG}
STUDENT_IMGS = {"id_doc": JPG, "face": PNG, "student_doc": WEBP}


@pytest.fixture
def vs(tmp_path):
    return VerificationStore(str(tmp_path / "v.db"), str(tmp_path / "files"))


def files(vs):
    return os.listdir(vs._dir)


class TestHelpers:
    def test_age_on_birthday_edges(self):
        assert age_on(date(2000, 11, 15), date(2026, 11, 15)) == 26
        assert age_on(date(2000, 11, 16), date(2026, 11, 15)) == 25
        assert age_on(date(2008, 11, 15), date(2026, 11, 14)) == 17

    def test_sniff(self):
        assert sniff_image(JPG) == "jpg" and sniff_image(PNG) == "png" and sniff_image(WEBP) == "webp"
        assert sniff_image(b"GIF89a....") is None and sniff_image(b"") is None
        assert sniff_image(b"<html>") is None


class TestSubmit:
    def test_adult_ok_and_files_written(self, vs):
        vid = vs.submit("a1", "adult", date(1990, 1, 1), ADULT_IMGS, T0)
        assert vid == 1 and len(files(vs)) == 2
        assert vs.status("a1")["status"] == "pending"
        assert vs.access_level("a1", T0) == "none"          # pendiente = sin acceso

    def test_file_permissions_private(self, vs):
        vs.submit("a1", "adult", date(1990, 1, 1), ADULT_IMGS, T0)
        for f in files(vs):
            assert oct(os.stat(os.path.join(vs._dir, f)).st_mode & 0o777) == "0o600"

    @pytest.mark.parametrize("birth", [date(2008, 11, 16), date(2012, 1, 1), date(2026, 1, 1)])
    def test_minors_rejected_without_storing_anything(self, vs, birth):
        with pytest.raises(VerificationError, match="18"):
            vs.submit("m", "adult", birth, ADULT_IMGS, T0)
        assert files(vs) == [] and vs.status("m")["status"] == "none"

    def test_exactly_18_accepted(self, vs):
        vs.submit("a", "adult", date(2008, 11, 15), ADULT_IMGS, T0)

    def test_future_birth_and_bad_types(self, vs):
        for b in (date(2027, 1, 1), "1990-01-01", datetime(1990, 1, 1)):
            with pytest.raises(VerificationError):
                vs.submit("a", "adult", b, ADULT_IMGS, T0)

    def test_student_age_range(self, vs):
        vs.submit("s25", "adult_student", date(2001, 11, 16), STUDENT_IMGS, T0)    # 25 años
        with pytest.raises(VerificationError, match="18 a 25"):
            vs.submit("s26", "adult_student", date(2000, 11, 15), STUDENT_IMGS, T0)  # 26 años

    def test_wrong_document_set(self, vs):
        with pytest.raises(VerificationError):
            vs.submit("a", "adult", date(1990, 1, 1), {"id_doc": JPG}, T0)
        with pytest.raises(VerificationError):
            vs.submit("a", "adult", date(1990, 1, 1), {**ADULT_IMGS, "student_doc": JPG}, T0)
        with pytest.raises(VerificationError):
            vs.submit("a", "adult_student", date(2003, 1, 1), ADULT_IMGS, T0)
        assert files(vs) == []

    def test_bad_images(self, vs):
        for bad in (b"", b"GIF89a" + b"0" * 10, b"x" * 10, None, "texto"):
            with pytest.raises(VerificationError):
                vs.submit("a", "adult", date(1990, 1, 1), {"id_doc": bad, "face": PNG}, T0)
        with pytest.raises(VerificationError, match="5 MB"):
            vs.submit("a", "adult", date(1990, 1, 1), {"id_doc": JPG + b"0" * MAX_IMAGE_BYTES, "face": PNG}, T0)
        assert files(vs) == []

    def test_invalid_account_or_tier(self, vs):
        for acc in ("", None, 5):
            with pytest.raises(VerificationError):
                vs.submit(acc, "adult", date(1990, 1, 1), ADULT_IMGS, T0)
        with pytest.raises(VerificationError):
            vs.submit("a", "minor", date(1990, 1, 1), ADULT_IMGS, T0)

    def test_only_one_pending(self, vs):
        vs.submit("a", "adult", date(1990, 1, 1), ADULT_IMGS, T0)
        with pytest.raises(VerificationError, match="en revisión"):
            vs.submit("a", "adult", date(1990, 1, 1), ADULT_IMGS, T0)
        assert len(files(vs)) == 2

    def test_birth_date_only_while_pending(self, vs):
        import sqlite3
        dump = lambda: "\n".join(sqlite3.connect(vs._db_path).iterdump())
        v1 = vs.submit("a", "adult_student", date(2003, 5, 6), STUDENT_IMGS, T0)
        assert vs.list_pending()[0]["declared_birth"] == "2003-05-06" and "2003-05-06" in dump()
        vs.approve(v1, "s", T0)
        assert "2003-05-06" not in dump()
        v2 = vs.submit("b", "adult", date(1991, 7, 8), ADULT_IMGS, T0)
        vs.reject(v2, "s", "x", T0)
        v3 = vs.submit("c", "adult", date(1992, 9, 10), ADULT_IMGS, T0)
        vs.purge_due(T0 + timedelta(days=8))
        assert "1991-07-08" not in dump() and "1992-09-10" not in dump()

    def test_approve_revalidates_age_at_decision_time(self, vs):
        vid = vs.submit("a", "adult_student", date(2000, 11, 16), STUDENT_IMGS, T0)    # 25 hoy, 26 mañana
        with pytest.raises(VerificationError, match="ya no cumple"):
            vs.approve(vid, "s", T0 + timedelta(days=1))
        assert vs.status("a")["status"] == "pending" and vs.access_level("a", T0) == "none"
        vs.approve(vid, "s", T0)


class TestReview:
    def test_list_and_read_image(self, vs):
        vid = vs.submit("a", "adult", date(1990, 1, 1), ADULT_IMGS, T0)
        assert [p["account_id"] for p in vs.list_pending()] == ["a"]
        assert vs.read_image(vid, "face") == (PNG, "png")
        with pytest.raises(VerificationError):
            vs.read_image(vid, "student_doc")

    def test_approve_gives_access_and_keeps_images_24h(self, vs):
        vid = vs.submit("a", "adult", date(1990, 1, 1), ADULT_IMGS, T0)
        vs.approve(vid, "stalin", T0)
        assert vs.access_level("a", T0) == "adult" and vs.list_pending() == []
        assert vs.purge_due(T0 + timedelta(hours=23, minutes=59)) == 0 and len(files(vs)) == 2
        assert vs.purge_due(T0 + timedelta(hours=24)) == 2 and files(vs) == []
        assert vs.access_level("a", T0 + timedelta(days=400)) == "adult"       # acceso sigue
        with pytest.raises(VerificationError):
            vs.read_image(vid, "face")

    def test_purge_is_idempotent(self, vs):
        vid = vs.submit("a", "adult", date(1990, 1, 1), ADULT_IMGS, T0)
        vs.approve(vid, "s", T0)
        late = T0 + timedelta(days=2)
        assert vs.purge_due(late) == 2 and vs.purge_due(late) == 0

    def test_reject_deletes_immediately_no_access(self, vs):
        vid = vs.submit("a", "adult", date(1990, 1, 1), ADULT_IMGS, T0)
        vs.reject(vid, "stalin", "foto borrosa", T0)
        assert files(vs) == [] and vs.access_level("a", T0) == "none"
        assert vs.status("a")["status"] == "rejected"

    def test_cannot_decide_twice_or_unknown(self, vs):
        vid = vs.submit("a", "adult", date(1990, 1, 1), ADULT_IMGS, T0)
        vs.approve(vid, "s", T0)
        for fn in (lambda: vs.approve(vid, "s", T0), lambda: vs.reject(vid, "s", "x", T0),
                   lambda: vs.approve(999, "s", T0)):
            with pytest.raises(VerificationError):
                fn()

    def test_pending_expires_after_7_days_and_purges(self, vs):
        vs.submit("a", "adult", date(1990, 1, 1), ADULT_IMGS, T0)
        assert vs.purge_due(T0 + timedelta(days=6)) == 0
        assert vs.purge_due(T0 + timedelta(days=7)) == 2 and files(vs) == []
        assert vs.status("a")["status"] == "expired" and vs.list_pending() == []
        vs.submit("a", "adult", date(1990, 1, 1), ADULT_IMGS, T0 + timedelta(days=8))   # puede reintentar

    def test_three_rejections_block_then_window_passes(self, vs):
        for i in range(3):
            vid = vs.submit("a", "adult", date(1990, 1, 1), ADULT_IMGS, T0 + timedelta(minutes=i))
            vs.reject(vid, "s", "no", T0 + timedelta(minutes=i))
        with pytest.raises(VerificationError, match="rechazos"):
            vs.submit("a", "adult", date(1990, 1, 1), ADULT_IMGS, T0 + timedelta(days=1))
        vs.submit("a", "adult", date(1990, 1, 1), ADULT_IMGS, T0 + timedelta(days=31))


class TestAccessLevel:
    def test_student_downgrades_to_adult_on_26th_birthday(self, vs):
        vid = vs.submit("s", "adult_student", date(2001, 12, 1), STUDENT_IMGS, T0)    # 24 años
        vs.approve(vid, "s", T0)
        assert vs.access_level("s", T0) == "adult_student"
        assert vs.access_level("s", datetime(2027, 11, 30, tzinfo=timezone.utc)) == "adult_student"   # 25
        assert vs.access_level("s", datetime(2027, 12, 1, tzinfo=timezone.utc)) == "adult"           # cumple 26
        assert vs.access_level("s", datetime(2030, 1, 1, tzinfo=timezone.utc)) == "adult"

    def test_leap_day_birth(self, vs):
        t = datetime(2025, 6, 1, tzinfo=timezone.utc)                  # 25 años
        vid = vs.submit("l", "adult_student", date(2000, 2, 29), STUDENT_IMGS, t)
        vs.approve(vid, "s", t)
        assert vs.access_level("l", datetime(2026, 2, 27, tzinfo=timezone.utc)) == "adult_student"
        assert vs.access_level("l", datetime(2026, 2, 28, tzinfo=timezone.utc)) == "adult"

    def test_unknown_and_corrupt_are_closed(self, vs):
        assert vs.access_level("nadie", T0) == "none" and vs.status("nadie") == {"status": "none"}
        vid = vs.submit("c", "adult_student", date(2003, 1, 1), STUDENT_IMGS, T0)
        vs.approve(vid, "s", T0)
        import sqlite3
        con = sqlite3.connect(vs._db_path)
        con.execute("UPDATE verifications SET student_until='basura'")
        con.commit()
        con.close()
        assert vs.access_level("c", T0) == "none"

    def test_accounts_are_isolated(self, vs):
        vid = vs.submit("a", "adult", date(1990, 1, 1), ADULT_IMGS, T0)
        vs.approve(vid, "s", T0)
        assert vs.access_level("b", T0) == "none"


class TestConsent:
    def _verified(self, vs, acc="a"):
        vid = vs.submit(acc, "adult", date(1990, 1, 1), ADULT_IMGS, T0)
        vs.approve(vid, "s", T0)

    def test_requires_verification(self, vs):
        with pytest.raises(VerificationError, match="verifiques|verificarte"):
            vs.grant_consent("a", "intimate_measure", CONSENT_TEXT_VERSION, T0)
        assert vs.can_use_intimate_measure("a", T0) is False

    def test_verified_without_consent_is_denied(self, vs):
        self._verified(vs)
        assert vs.can_use_intimate_measure("a", T0) is False

    def test_grant_and_revoke(self, vs):
        self._verified(vs)
        vs.grant_consent("a", "intimate_measure", CONSENT_TEXT_VERSION, T0)
        assert vs.can_use_intimate_measure("a", T0) is True
        vs.revoke_consent("a", "intimate_measure")
        assert vs.can_use_intimate_measure("a", T0) is False

    def test_wrong_version_or_kind(self, vs):
        self._verified(vs)
        with pytest.raises(VerificationError):
            vs.grant_consent("a", "intimate_measure", "vieja", T0)
        with pytest.raises(VerificationError):
            vs.grant_consent("a", "otra", CONSENT_TEXT_VERSION, T0)

    def test_old_text_version_invalidates(self, vs):
        self._verified(vs)
        vs.grant_consent("a", "intimate_measure", CONSENT_TEXT_VERSION, T0)
        import sqlite3
        con = sqlite3.connect(vs._db_path)
        con.execute("UPDATE consents SET text_version='2020-01-01'")
        con.commit()
        con.close()
        assert vs.can_use_intimate_measure("a", T0) is False


class TestDeleteAccountData:
    def test_removes_everything_of_that_account_only(self, vs):
        v1 = vs.submit("a", "adult", date(1990, 1, 1), ADULT_IMGS, T0)
        vs.approve(v1, "s", T0)
        vs.grant_consent("a", "intimate_measure", CONSENT_TEXT_VERSION, T0)
        vs.submit("b", "adult", date(1990, 1, 1), ADULT_IMGS, T0)
        assert vs.delete_account_data("a") == 2
        assert vs.status("a") == {"status": "none"} and vs.access_level("a", T0) == "none"
        assert vs.can_use_intimate_measure("a", T0) is False
        assert len(files(vs)) == 2 and vs.status("b")["status"] == "pending"

    def test_unknown_account_is_noop(self, vs):
        assert vs.delete_account_data("nadie") == 0


class TestSchemaMigrationAndConsentRecord:
    def test_old_database_gets_docs_consent_column(self, tmp_path):
        import sqlite3
        db = str(tmp_path / "old.db")
        con = sqlite3.connect(db)
        con.execute("""CREATE TABLE verifications(id INTEGER PRIMARY KEY AUTOINCREMENT, account_id TEXT NOT NULL,
            tier TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL, decided_at TEXT, decided_by TEXT,
            reject_reason TEXT, student_until TEXT, declared_birth TEXT, purge_at TEXT NOT NULL,
            images_purged INTEGER NOT NULL DEFAULT 0)""")
        con.commit()
        con.close()
        vs = VerificationStore(db, str(tmp_path / "f"))
        vs.submit("a", "adult", date(1990, 1, 1), ADULT_IMGS, T0, docs_consent_version="2026-11-16")
        assert sqlite3.connect(db).execute("SELECT docs_consent FROM verifications").fetchone()[0] == "2026-11-16"
        VerificationStore(db, str(tmp_path / "f"))        # abrir de nuevo no falla
