# tests/unit/test_fons_operators.py
"""
* UBICACIÓN: OmniaMentis/tests/unit/test_fons_operators.py
* PROPÓSITO: Tests de los revisores con nombre del Fons: tokens con identidad,
*            lista de revisores, bitácora de auditoría y script de administración.
* CREADO: 2026-10-20
* ESTADO: Test Permanente
"""

import base64
import hashlib
import hmac
import importlib.util
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT / "src"))

from core.auth import fons_auth as fa
from core.auth.fons_audit import FonsAudit, MAX_FIELD_CHARS

SECRET = "clave-de-prueba-0123456789"
H = fa.hash_password("una-clave-larga-123")


def _forge(prefix, expiry, secret=SECRET):
    payload = f"{prefix}:{expiry}"
    sig = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return base64.urlsafe_b64encode(f"{payload}:{sig}".encode()).decode()


class TestTokens:
    def test_legacy_token_still_works_and_is_operator_fons(self):
        t = fa.create_session_token(SECRET)
        assert fa.verify_session_token(t, SECRET) and fa.token_operator(t, SECRET) == "fons"

    def test_named_token_carries_the_name(self):
        t = fa.create_session_token(SECRET, operator="ana")
        assert fa.token_operator(t, SECRET) == "ana" and fa.verify_session_token(t, SECRET)

    @pytest.mark.parametrize("bad", ["Ana", "a", "1ana", "ana smith", "a:b", "", "x" * 40, "../x"])
    def test_invalid_operator_name_is_refused(self, bad):
        with pytest.raises(ValueError):
            fa.create_session_token(SECRET, operator=bad)

    def test_wrong_secret_expired_and_tampered_are_rejected(self):
        t = fa.create_session_token(SECRET, operator="ana")
        assert fa.token_operator(t, "otra-clave") is None
        assert fa.token_operator(_forge("fons.ana", int(time.time()) - 5), SECRET) is None
        # cambiar el nombre sin volver a firmar no sirve
        raw = base64.urlsafe_b64decode(t).decode().replace("fons.ana", "fons.luis")
        assert fa.token_operator(base64.urlsafe_b64encode(raw.encode()).decode(), SECRET) is None
        assert fa.token_operator(_forge("fons.Ana", int(time.time()) + 60), SECRET) is None
        assert fa.token_operator(_forge("admin", int(time.time()) + 60), SECRET) is None

    @pytest.mark.parametrize("tok", ["", None, "basura", "YWJj", "a" * 500])
    def test_garbage_tokens(self, tok):
        assert fa.token_operator(tok, SECRET) is None and fa.verify_session_token(tok, SECRET) is False

    def test_empty_secret_never_validates(self):
        assert fa.token_operator(_forge("fons", int(time.time()) + 60, ""), "") is None


class TestParseOperators:
    def test_parses_valid_entries(self):
        assert fa.parse_operators(f"ana:{H},luis:{H}") == {"ana": H, "luis": H}

    def test_ignores_malformed_and_duplicates(self):
        raw = f"Ana:{H},x:{H},ok:corto,sinhash,:{H},ana:{H},ana:{fa.hash_password('otra-clave-larga')}"
        assert fa.parse_operators(raw) == {"ana": H}

    @pytest.mark.parametrize("raw", ["", None, "   ", ",,,"])
    def test_empty(self, raw):
        assert fa.parse_operators(raw) == {}


class TestAudit:
    def test_records_and_reads_newest_first(self, tmp_path):
        a = FonsAudit(tmp_path / "x" / "audit.jsonl")
        a.record("login_ok", "ana", ip="1.2.3.4")
        a.record("decision", "ana", consultation_id="ETH-0001", action="approved", approved=True)
        ev = a.recent(10)
        assert [e["event"] for e in ev] == ["decision", "login_ok"]
        assert ev[0]["consultation_id"] == "ETH-0001" and ev[0]["approved"] is True and ev[0]["operator"] == "ana"

    def test_unknown_event_is_refused(self, tmp_path):
        with pytest.raises(ValueError):
            FonsAudit(tmp_path / "a.jsonl").record("borrar_todo", "ana")

    def test_fields_are_sanitized_and_cannot_overwrite_core_keys(self, tmp_path):
        a = FonsAudit(tmp_path / "a.jsonl")
        a.record("login_fail", "ana\nmalo", note="x" * 1000, ts="hoy", nested={"a": 1})
        e = a.recent(1)[0]
        assert e["event"] == "login_fail" and isinstance(e["ts"], float)
        assert "\n" not in e["operator"] and len(e["note"]) == MAX_FIELD_CHARS
        assert isinstance(e["nested"], str)          # nada de estructuras anidadas
        assert len((tmp_path / "a.jsonl").read_text().splitlines()) == 1

    def test_damaged_lines_are_skipped(self, tmp_path):
        p = tmp_path / "a.jsonl"
        a = FonsAudit(p)
        a.record("login_ok", "ana")
        with open(p, "a") as fh:
            fh.write("esto no es json\n[1,2]\n")
        a.record("login_ok", "luis")
        assert [e["operator"] for e in a.recent(10)] == ["luis", "ana"]

    @pytest.mark.parametrize("limit,expected", [(1, 1), (0, 3), (-4, 3), (True, 3), ("x", 3), (999, 3), (2, 2)])
    def test_limit_handling(self, tmp_path, limit, expected):
        a = FonsAudit(tmp_path / "a.jsonl")
        for i in range(3):
            a.record("login_ok", f"op{i}")
        assert len(a.recent(limit)) == expected

    def test_rotation_keeps_disk_bounded(self, tmp_path):
        p = tmp_path / "a.jsonl"
        a = FonsAudit(p, max_bytes=400)
        for i in range(40):
            a.record("login_ok", "ana", n=i)
        assert p.stat().st_size <= 400 and (tmp_path / "a.jsonl.1").exists()
        assert a.recent(1)[0]["n"] == 39

    def test_write_failure_returns_false_not_raises(self, tmp_path):
        d = tmp_path / "a.jsonl"
        a = FonsAudit(d)
        d.mkdir()                                    # el "archivo" es una carpeta: escribir falla
        assert a.record("login_ok", "ana") is False
        assert a.recent(5) == []

    def test_empty_when_file_missing(self, tmp_path):
        assert FonsAudit(tmp_path / "nada.jsonl").recent(5) == []


def _load_script():
    spec = importlib.util.spec_from_file_location("fons_operator_script", ROOT / "scripts" / "fons_operator.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestAdminScript:
    def test_add_creates_secret_once_and_never_rotates_it(self):
        m = _load_script()
        lines = m.add_operator(["OTRA=1"], "ana", "contraseña-larga-1")
        secret = m.get_value(lines, "FONS_SECRET_KEY")
        assert len(secret) == 64 and "OTRA=1" in lines
        lines = m.add_operator(lines, "luis", "contraseña-larga-2")
        assert m.get_value(lines, "FONS_SECRET_KEY") == secret
        ops = fa.parse_operators(m.get_value(lines, "FONS_OPERATORS"))
        assert set(ops) == {"ana", "luis"}
        assert fa.verify_password("contraseña-larga-1", ops["ana"]) and not fa.verify_password("contraseña-larga-1", ops["luis"])

    def test_add_existing_changes_password(self):
        m = _load_script()
        lines = m.add_operator([], "ana", "contraseña-larga-1")
        lines = m.add_operator(lines, "ana", "contraseña-nueva-2")
        ops = fa.parse_operators(m.get_value(lines, "FONS_OPERATORS"))
        assert list(ops) == ["ana"] and fa.verify_password("contraseña-nueva-2", ops["ana"])

    @pytest.mark.parametrize("name,pw", [("fons", "contraseña-larga-1"), ("Ana", "contraseña-larga-1"),
                                         ("a", "contraseña-larga-1"), ("ana", "corta")])
    def test_add_rejects_bad_input(self, name, pw):
        with pytest.raises(ValueError):
            _load_script().add_operator([], name, pw)

    def test_remove(self):
        m = _load_script()
        lines = m.add_operator(m.add_operator([], "ana", "contraseña-larga-1"), "luis", "contraseña-larga-2")
        lines = m.remove_operator(lines, "ana")
        assert list(fa.parse_operators(m.get_value(lines, "FONS_OPERATORS"))) == ["luis"]
        with pytest.raises(ValueError):
            m.remove_operator(lines, "ana")

    def test_main_end_to_end_with_temp_env(self, tmp_path, monkeypatch, capsys):
        m = _load_script()
        monkeypatch.setattr(m, "ENV_FILE", tmp_path / ".env")
        pws = iter(["contraseña-larga-1", "contraseña-larga-1"])
        monkeypatch.setattr(m.getpass, "getpass", lambda *_: next(pws))
        assert m.main(["add", "ana"]) == 0
        assert "FONS_OPERATORS=ana:" in (tmp_path / ".env").read_text()
        assert m.main(["list"]) == 0 and "ana" in capsys.readouterr().out
        assert m.main(["remove", "ana"]) == 0
        assert m.main(["remove", "ana"]) == 1
        assert m.main(["add"]) == 2
        pws2 = iter(["contraseña-larga-1", "otra-distinta-999"])
        monkeypatch.setattr(m.getpass, "getpass", lambda *_: next(pws2))
        assert m.main(["add", "luis"]) == 1
