# tests/unit/test_guardian_mail.py
"""
* UBICACIÓN: OmniaMentis/tests/unit/test_guardian_mail.py
* PROPÓSITO: Tests de src/core/auth/guardian_mail.py (correo con el enlace de
*            confirmación del representante legal de 13-14 años). Sin red:
*            smtplib se sustituye por dobles.
* CREADO: 2026-10-14
* ESTADO: Test Permanente
"""

import logging
import smtplib
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from core.auth import guardian_mail as gm

_VARS = (
    "OMNIA_SMTP_HOST", "OMNIA_SMTP_PORT", "OMNIA_SMTP_USER", "OMNIA_SMTP_PASSWORD",
    "OMNIA_SMTP_FROM", "OMNIA_SMTP_SECURITY", "OMNIA_PUBLIC_URL", "OMNIA_DEV_PRINT_GUARDIAN_LINK",
)
TOKEN = "T" * 43


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for v in _VARS:
        monkeypatch.delenv(v, raising=False)


def _smtp_env(monkeypatch, **over):
    env = {"OMNIA_SMTP_HOST": "smtp.test", "OMNIA_SMTP_FROM": "no-reply@test.example"}
    env.update(over)
    for k, v in env.items():
        monkeypatch.setenv(k, v)


class _FakeSMTP:
    instances = []
    fail_on = None

    def __init__(self, host, port, timeout=None, context=None):
        self.host, self.port, self.timeout, self.context = host, port, timeout, context
        self.calls, self.sent = [], []
        _FakeSMTP.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def starttls(self, context=None):
        self.calls.append("starttls")
        if _FakeSMTP.fail_on == "starttls":
            raise smtplib.SMTPException("tls")

    def login(self, user, password):
        self.calls.append(("login", user, password))
        if _FakeSMTP.fail_on == "login":
            raise smtplib.SMTPAuthenticationError(535, b"no")

    def send_message(self, msg):
        self.calls.append("send")
        if _FakeSMTP.fail_on == "send":
            raise smtplib.SMTPRecipientsRefused({})
        self.sent.append(msg)


class _FakeSMTPSSL(_FakeSMTP):
    pass


@pytest.fixture
def fake_smtp(monkeypatch):
    _FakeSMTP.instances = []
    _FakeSMTP.fail_on = None
    monkeypatch.setattr(gm.smtplib, "SMTP", _FakeSMTP)
    monkeypatch.setattr(gm.smtplib, "SMTP_SSL", _FakeSMTPSSL)
    return _FakeSMTP


class TestConfiguration:

    def test_unconfigured_by_default(self):
        assert gm.is_configured() is False

    def test_host_alone_is_not_enough(self, monkeypatch):
        monkeypatch.setenv("OMNIA_SMTP_HOST", "smtp.test")
        assert gm.is_configured() is False

    def test_from_alone_is_not_enough(self, monkeypatch):
        monkeypatch.setenv("OMNIA_SMTP_FROM", "a@b.example")
        assert gm.is_configured() is False

    def test_host_and_from_configure_it(self, monkeypatch):
        _smtp_env(monkeypatch)
        assert gm.is_configured() is True

    @pytest.mark.parametrize("value,expected", [
        ("true", True), ("1", True), ("YES", True), ("on", True),
        ("false", False), ("0", False), ("", False), ("nope", False),
    ])
    def test_dev_flag(self, monkeypatch, value, expected):
        monkeypatch.setenv("OMNIA_DEV_PRINT_GUARDIAN_LINK", value)
        assert gm.dev_print_mode() is expected
        assert gm.is_configured() is expected

    def test_whitespace_in_env_is_ignored(self, monkeypatch):
        _smtp_env(monkeypatch, OMNIA_SMTP_HOST="  smtp.test  ")
        assert gm.is_configured() is True


class TestLink:

    def test_default_public_url(self):
        assert gm.build_link(TOKEN) == f"http://127.0.0.1:8080/representante.html#t={TOKEN}"

    def test_custom_public_url_without_trailing_slash(self, monkeypatch):
        monkeypatch.setenv("OMNIA_PUBLIC_URL", "https://omnia.example/")
        assert gm.build_link(TOKEN) == f"https://omnia.example/representante.html#t={TOKEN}"

    @pytest.mark.parametrize("configured,expected_base", [
        ("http://127.0.0.1:8080/representante.html", "http://127.0.0.1:8080"),       # error real visto en un .env
        ("http://127.0.0.1:8080/omnia_dashboard.html", "http://127.0.0.1:8080"),
        ("https://omnia.example/app/omnia_dashboard.html", "https://omnia.example/app"),
        ("https://omnia.example/app/", "https://omnia.example/app"),
        ("https://omnia.example//", "https://omnia.example"),
        ("  https://omnia.example  ", "https://omnia.example"),
        ("https://omnia.example/?x=1#frag", "https://omnia.example"),
    ])
    def test_public_url_is_normalised(self, monkeypatch, configured, expected_base):
        monkeypatch.setenv("OMNIA_PUBLIC_URL", configured)
        assert gm.build_link(TOKEN) == f"{expected_base}/representante.html#t={TOKEN}"

    @pytest.mark.parametrize("bad", ["omnia.example", "ftp://omnia.example", "javascript:alert(1)", "://x", "/solo/ruta"])
    def test_invalid_public_url_falls_back_to_dev_address(self, monkeypatch, bad):
        monkeypatch.setenv("OMNIA_PUBLIC_URL", bad)
        assert gm.build_link(TOKEN) == f"http://127.0.0.1:8080/representante.html#t={TOKEN}"

    def test_token_goes_in_the_fragment_not_the_query(self):
        link = gm.build_link(TOKEN)
        assert "?" not in link and "#t=" in link


class TestMessage:

    def test_contents(self, monkeypatch):
        _smtp_env(monkeypatch)
        msg = gm.build_message(" mama@example.com", "http://x/representante.html#t=abc",
                               "nino@example.com", "Luis")
        body = msg.get_content()
        assert msg["To"].strip() == "mama@example.com"
        assert msg["From"] == "no-reply@test.example"
        assert "Luis (nino@example.com)" in body
        assert "http://x/representante.html#t=abc" in body
        assert "7 días" in body and "911" in body
        assert "no es un servicio de salud ni de emergencias" in body

    def test_without_name_uses_the_email(self, monkeypatch):
        _smtp_env(monkeypatch)
        body = gm.build_message("m@example.com", "http://x", "nino@example.com", None).get_content()
        assert "nino@example.com quiere crear una cuenta" in body

    def test_name_cannot_inject_headers_or_lines(self, monkeypatch):
        _smtp_env(monkeypatch)
        msg = gm.build_message("m@example.com", "http://x", "n@example.com",
                               "Luis\r\nBcc: victima@example.com")
        assert msg["Bcc"] is None
        assert "\r" not in msg.get_content().split("quiere")[0]

    def test_no_password_or_recovery_data(self, monkeypatch):
        _smtp_env(monkeypatch)
        body = gm.build_message("m@example.com", "http://x", "n@example.com", None).get_content().lower()
        assert "contraseña" not in body and "recuperación" not in body


class TestDevMode:

    def test_prints_the_link_and_sends_nothing(self, monkeypatch, capsys, fake_smtp):
        monkeypatch.setenv("OMNIA_DEV_PRINT_GUARDIAN_LINK", "true")
        gm.send_guardian_link("mama@example.com", TOKEN, "nino@example.com")
        out = capsys.readouterr().out
        assert f"representante.html#t={TOKEN}" in out and "mama@example.com" in out
        assert fake_smtp.instances == []

    def test_dev_mode_wins_over_smtp(self, monkeypatch, capsys, fake_smtp):
        _smtp_env(monkeypatch)
        monkeypatch.setenv("OMNIA_DEV_PRINT_GUARDIAN_LINK", "1")
        gm.send_guardian_link("mama@example.com", TOKEN, "nino@example.com")
        assert fake_smtp.instances == []


class TestSmtp:

    def test_starttls_login_and_send(self, monkeypatch, fake_smtp):
        _smtp_env(monkeypatch, OMNIA_SMTP_USER="user", OMNIA_SMTP_PASSWORD="pw", OMNIA_SMTP_PORT="2525")
        gm.send_guardian_link("mama@example.com", TOKEN, "nino@example.com", "Luis")
        s = fake_smtp.instances[0]
        assert (s.host, s.port, s.timeout) == ("smtp.test", 2525, gm.SMTP_TIMEOUT_SECONDS)
        assert s.calls == ["starttls", ("login", "user", "pw"), "send"]
        assert s.sent[0]["To"] == "mama@example.com"
        assert TOKEN in s.sent[0].get_content()

    def test_default_port_is_587(self, monkeypatch, fake_smtp):
        _smtp_env(monkeypatch)
        gm.send_guardian_link("m@example.com", TOKEN, "n@example.com")
        assert fake_smtp.instances[0].port == 587

    def test_no_login_without_user(self, monkeypatch, fake_smtp):
        _smtp_env(monkeypatch)
        gm.send_guardian_link("m@example.com", TOKEN, "n@example.com")
        assert all(not (isinstance(c, tuple) and c[0] == "login") for c in fake_smtp.instances[0].calls)

    def test_ssl_mode_uses_smtp_ssl_without_starttls(self, monkeypatch, fake_smtp):
        _smtp_env(monkeypatch, OMNIA_SMTP_SECURITY="ssl", OMNIA_SMTP_PORT="465")
        gm.send_guardian_link("m@example.com", TOKEN, "n@example.com")
        s = fake_smtp.instances[0]
        assert isinstance(s, _FakeSMTPSSL) and "starttls" not in s.calls and s.port == 465

    def test_none_security_skips_starttls(self, monkeypatch, fake_smtp):
        _smtp_env(monkeypatch, OMNIA_SMTP_SECURITY="none")
        gm.send_guardian_link("m@example.com", TOKEN, "n@example.com")
        assert "starttls" not in fake_smtp.instances[0].calls

    @pytest.mark.parametrize("stage", ["starttls", "login", "send"])
    def test_smtp_failures_become_mail_error(self, monkeypatch, fake_smtp, stage):
        _smtp_env(monkeypatch, OMNIA_SMTP_USER="user", OMNIA_SMTP_PASSWORD="pw")
        fake_smtp.fail_on = stage
        with pytest.raises(gm.MailError):
            gm.send_guardian_link("m@example.com", TOKEN, "n@example.com")

    def test_network_errors_become_mail_error(self, monkeypatch):
        _smtp_env(monkeypatch)

        def boom(*a, **k):
            raise OSError("sin red")
        monkeypatch.setattr(gm.smtplib, "SMTP", boom)
        with pytest.raises(gm.MailError):
            gm.send_guardian_link("m@example.com", TOKEN, "n@example.com")

    def test_unconfigured_raises(self):
        with pytest.raises(gm.MailError):
            gm.send_guardian_link("m@example.com", TOKEN, "n@example.com")

    def test_invalid_port_raises(self, monkeypatch, fake_smtp):
        _smtp_env(monkeypatch, OMNIA_SMTP_PORT="abc")
        with pytest.raises(gm.MailError):
            gm.send_guardian_link("m@example.com", TOKEN, "n@example.com")
        assert fake_smtp.instances == []

    def test_failure_logs_neither_recipient_nor_token(self, monkeypatch, fake_smtp, caplog):
        _smtp_env(monkeypatch)
        fake_smtp.fail_on = "send"
        with caplog.at_level(logging.DEBUG, logger="omnia.guardian_mail"):
            with pytest.raises(gm.MailError):
                gm.send_guardian_link("secreto@example.com", TOKEN, "n@example.com")
        assert "secreto@example.com" not in caplog.text and TOKEN not in caplog.text
        assert "SMTPRecipientsRefused" in caplog.text


# ---------------------------------------------------------------------------
# Envío REAL por socket (sin dobles de smtplib): un servidor SMTP mínimo en
# 127.0.0.1 recibe el mensaje tal como lo enviaría un servidor de correo.
# Cubre la ruta "none" (sin TLS ni login); STARTTLS/SSL y la autenticación
# dependen del proveedor y se prueban con el SMTP real (ver README).
# ---------------------------------------------------------------------------

import socketserver
import threading
from email import message_from_bytes
from email import policy


class _MiniSMTP(socketserver.StreamRequestHandler):
    received = []

    def _send(self, line):
        self.wfile.write((line + "\r\n").encode())

    def handle(self):
        self._send("220 mini ESMTP")
        data_mode, buf, envelope = False, [], {}
        while True:
            raw = self.rfile.readline()
            if not raw:
                return
            line = raw.decode("utf-8", "replace").rstrip("\r\n")
            if data_mode:
                if line == ".":
                    data_mode = False
                    _MiniSMTP.received.append({"envelope": dict(envelope), "data": "\r\n".join(buf).encode()})
                    buf = []
                    self._send("250 OK queued")
                else:
                    buf.append(line[1:] if line.startswith("..") else line)
                continue
            cmd = line.upper()
            if cmd.startswith("EHLO"):
                self._send("250-mini")
                self._send("250 8BITMIME")
            elif cmd.startswith("HELO"):
                self._send("250 mini")
            elif cmd.startswith("MAIL FROM"):
                envelope["from"] = line.split(":", 1)[1].strip()
                self._send("250 OK")
            elif cmd.startswith("RCPT TO"):
                envelope["to"] = line.split(":", 1)[1].strip()
                self._send("250 OK")
            elif cmd == "DATA":
                data_mode = True
                self._send("354 go")
            elif cmd == "QUIT":
                self._send("221 bye")
                return
            else:
                self._send("250 OK")


@pytest.fixture
def mini_smtp():
    _MiniSMTP.received = []
    server = socketserver.ThreadingTCPServer(("127.0.0.1", 0), _MiniSMTP)
    server.daemon_threads = True
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    yield server.server_address[1]
    server.shutdown()
    server.server_close()


class TestRealSocket:

    def test_the_message_really_arrives_with_the_link(self, monkeypatch, mini_smtp):
        _smtp_env(monkeypatch, OMNIA_SMTP_HOST="127.0.0.1", OMNIA_SMTP_PORT=str(mini_smtp),
                  OMNIA_SMTP_SECURITY="none", OMNIA_PUBLIC_URL="https://omnia.example")
        gm.send_guardian_link("mama@example.com", TOKEN, "nino@example.com", "Luis")
        assert len(_MiniSMTP.received) == 1
        got = _MiniSMTP.received[0]
        assert "mama@example.com" in got["envelope"]["to"]
        assert "no-reply@test.example" in got["envelope"]["from"]
        msg = message_from_bytes(got["data"], policy=policy.default)
        assert msg["To"] == "mama@example.com"
        assert "Autorización de representante legal" in msg["Subject"]
        body = msg.get_body().get_content()
        assert f"https://omnia.example/representante.html#t={TOKEN}" in body
        assert "Luis (nino@example.com)" in body

    def test_accented_subject_and_body_survive_the_wire(self, monkeypatch, mini_smtp):
        _smtp_env(monkeypatch, OMNIA_SMTP_HOST="127.0.0.1", OMNIA_SMTP_PORT=str(mini_smtp),
                  OMNIA_SMTP_SECURITY="none")
        gm.send_guardian_link("mama@example.com", TOKEN, "nino@example.com", "Ñandú Pérez")
        msg = message_from_bytes(_MiniSMTP.received[0]["data"], policy=policy.default)
        assert "representante" in msg["Subject"] and "Ñandú Pérez" in msg.get_body().get_content()

    def test_connection_refused_becomes_mail_error(self, monkeypatch):
        import socket
        s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
        _smtp_env(monkeypatch, OMNIA_SMTP_HOST="127.0.0.1", OMNIA_SMTP_PORT=str(port),
                  OMNIA_SMTP_SECURITY="none")
        with pytest.raises(gm.MailError):
            gm.send_guardian_link("mama@example.com", TOKEN, "nino@example.com")