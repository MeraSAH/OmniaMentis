"""Lanzador de escritorio, PWA (manifiesto, service worker, iconos) y servicio del dashboard bajo /app/."""
import importlib.util
import json
import re
import socket
import sys
import struct
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "manifestation" / "web_interface"
_spec = importlib.util.spec_from_file_location("omnia_desktop", ROOT / "scripts" / "omnia_desktop.py")
od = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(od)


class TestFindFreePort:
    def test_prefers_the_requested_port_when_free(self):
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            free = s.getsockname()[1]
        assert od.find_free_port(free) == free

    def test_falls_back_when_taken(self):
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            s.listen()
            busy = s.getsockname()[1]
            got = od.find_free_port(busy)
        assert got != busy and 1024 <= got <= 65535


class TestBuildEnv:
    def test_local_only_and_serves_dashboard(self):
        env = od.build_env(Path("/x/omnia"), 8123, {"PATH": "/bin", "PYTHONPATH": "/otro"})
        assert env["HOST"] == "127.0.0.1" and env["PORT"] == "8123" and env["SERVE_DASHBOARD"] == "true"
        parts = env["PYTHONPATH"].split(":")
        assert parts[0].endswith("src") and parts[-1] == "/otro"
        assert env["PATH"] == "/bin"

    def test_does_not_mutate_the_base_env(self):
        base = {"A": "1"}
        od.build_env(Path("/x"), 1, base)
        assert base == {"A": "1"}


class TestFindBrowser:
    def test_linux_first_available(self):
        found = {"chromium": "/usr/bin/chromium"}
        assert od.find_browser("linux", which=found.get) == "/usr/bin/chromium"

    def test_linux_none(self):
        assert od.find_browser("linux", which=lambda n: None) is None

    def test_windows_picks_first_existing_path(self):
        def expand(p):
            return (p.replace("%ProgramFiles(x86)%", "C:/PF86").replace("%ProgramFiles%", "C:/PF")
                    .replace("%LocalAppData%", "C:/LA"))
        edge = expand(r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe")
        assert od.find_browser("win32", exists=lambda p: p == edge, expand=expand) == edge

    def test_windows_unexpanded_variable_is_skipped(self):
        assert od.find_browser("win32", exists=lambda p: True, expand=lambda p: p) is None

    def test_app_command(self):
        cmd = od.app_command("/b", "http://127.0.0.1:1/app/", Path("/p"))
        assert cmd[0] == "/b" and "--app=http://127.0.0.1:1/app/" in cmd and "--user-data-dir=/p" in cmd


class _Resp:
    def __init__(self, status):
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _fake_time():
    t = [0.0]

    def clock():
        return t[0]

    def sleep(d):
        t[0] += d
    return clock, sleep


class TestWaitForHealth:
    def test_ready_after_a_few_failures(self):
        calls = []

        def opener(url, timeout):
            calls.append(url)
            if len(calls) < 3:
                raise OSError("aún no")
            return _Resp(200)
        clock, sleep = _fake_time()
        assert od.wait_for_health("http://x/health", 30, 0.5, opener, sleep=sleep, clock=clock) is True
        assert len(calls) == 3

    def test_timeout(self):
        clock, sleep = _fake_time()

        def opener(url, timeout):
            raise OSError()
        assert od.wait_for_health("u", 2, 0.5, opener, sleep=sleep, clock=clock) is False

    def test_non_200_is_not_ready(self):
        clock, sleep = _fake_time()
        assert od.wait_for_health("u", 2, 0.5, lambda u, timeout: _Resp(503), sleep=sleep, clock=clock) is False

    def test_stops_when_server_died(self):
        clock, sleep = _fake_time()
        calls = []

        def opener(u, timeout):
            calls.append(1)
            return _Resp(200)
        assert od.wait_for_health("u", 60, 0.5, opener, alive=lambda: False, sleep=sleep, clock=clock) is False
        assert calls == []


class TestCheckEnvironment:
    def test_real_project_is_fine(self):
        assert od.check_environment(ROOT) == []

    def test_empty_folder_reports_problems(self, tmp_path):
        probs = od.check_environment(tmp_path)
        assert any("main_flask" in p for p in probs) and any("omnia_dashboard" in p for p in probs)

    def test_check_flag_exit_code_and_message(self, capsys):
        assert od.main(["--check"]) == 0
        assert "Todo listo" in capsys.readouterr().out


def _png_size(path):
    data = path.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    return struct.unpack(">II", data[16:24])


class TestPwaFiles:
    def test_manifest_is_valid_and_icons_exist_with_declared_size(self):
        m = json.loads((WEB / "manifest.webmanifest").read_text(encoding="utf-8"))
        assert m["display"] == "standalone" and m["start_url"].endswith("omnia_dashboard.html")
        assert m["name"] and m["short_name"] and m["background_color"].startswith("#")
        assert {"any", "maskable"} <= {i["purpose"] for i in m["icons"]}
        for i in m["icons"]:
            w, h = (int(x) for x in i["sizes"].split("x"))
            assert _png_size(WEB / i["src"]) == (w, h)
        assert {"192x192", "512x512"} <= {i["sizes"] for i in m["icons"]}

    def test_service_worker_never_touches_the_api(self):
        sw = (WEB / "sw.js").read_text(encoding="utf-8")
        assert "'/api/'" in sw and "req.method !== 'GET'" in sw and "url.origin !== self.location.origin" in sw
        assert "POST" not in sw and "indexedDB" not in sw

    def test_service_worker_shell_files_exist(self):
        sw = (WEB / "sw.js").read_text(encoding="utf-8")
        shell = re.search(r"const SHELL = \[(.*?)\];", sw, re.S).group(1)
        rels = re.findall(r"'\./([^']+)'", shell)
        assert rels
        for rel in rels:
            assert (WEB / rel).is_file(), rel

    def test_dashboard_links_manifest_and_registers_worker(self):
        html = (WEB / "omnia_dashboard.html").read_text(encoding="utf-8")
        assert 'rel="manifest" href="manifest.webmanifest"' in html and "register('sw.js')" in html
        assert 'name="theme-color"' in html and "startsWith('/app/')" in html


class TestDashboardServing:
    @pytest.fixture
    def fm(self):
        import api.main_flask as m
        return m

    def test_disabled_by_default(self, fm, monkeypatch):
        monkeypatch.delenv("SERVE_DASHBOARD", raising=False)
        c = fm.app.test_client()
        assert c.get("/app/").status_code == 404 and c.get("/app/sw.js").status_code == 404

    def test_enabled_serves_dashboard_and_files(self, fm, monkeypatch):
        monkeypatch.setenv("SERVE_DASHBOARD", "true")
        c = fm.app.test_client()
        for path, ctype in (("/app/", "text/html"), ("/app/omnia_dashboard.html", "text/html"),
                            ("/app/sw.js", "javascript"), ("/app/manifest.webmanifest", "manifest+json"),
                            ("/app/icons/icon-192.png", "image/png"), ("/app/legal/privacidad.html", "text/html")):
            r = c.get(path)
            assert r.status_code == 200, path
            assert ctype in r.headers["Content-Type"], path
            assert r.headers["Cache-Control"] == "no-cache"

    def test_app_without_slash_redirects_so_relative_paths_work(self, fm, monkeypatch):
        monkeypatch.setenv("SERVE_DASHBOARD", "true")
        r = fm.app.test_client().get("/app")
        assert r.status_code in (301, 308) and r.headers["Location"].endswith("/app/")

    def test_does_not_leak_other_files(self, fm, monkeypatch):
        monkeypatch.setenv("SERVE_DASHBOARD", "true")
        c = fm.app.test_client()
        for path in ("/app/x.py", "/app/../../src/api/main_flask.py", "/app/%2e%2e/%2e%2e/.env", "/app/.env",
                     "/app/nope.html", "/app/icons/"):
            assert c.get(path).status_code == 404, path

    def test_static_files_do_not_spend_the_api_rate_limit(self, fm, monkeypatch):
        monkeypatch.setenv("SERVE_DASHBOARD", "true")
        fm._rate_data.clear()
        c = fm.app.test_client()
        for _ in range(60):
            assert c.get("/app/sw.js").status_code == 200
        assert fm._rate_data == {}


class TestFrozenExe:
    """Lo que cambia cuando el lanzador corre empaquetado como OmniaMentis.exe (simulado: aquí no se puede compilar)."""

    def test_not_frozen_uses_the_current_python(self):
        assert od.find_python(Path("/p"), frozen=False, current="/usr/bin/py") == "/usr/bin/py"

    def test_frozen_prefers_project_venv_on_windows(self):
        venv = str(Path("/p") / ".venv/Scripts/python.exe")
        assert od.find_python(Path("/p"), "win32", True, which=lambda n: "C:/otro/python.exe", exists=lambda x: x == venv) == venv

    def test_frozen_prefers_project_venv_on_linux(self):
        venv = str(Path("/p") / ".venv/bin/python")
        assert od.find_python(Path("/p"), "linux", True, which=lambda n: "/usr/bin/python3", exists=lambda x: x == venv) == venv

    def test_frozen_falls_back_to_system_python(self):
        found = {"python": "C:/Python/python.exe"}
        assert od.find_python(Path("/p"), "win32", True, which=found.get, exists=lambda x: False) == "C:/Python/python.exe"
        assert od.find_python(Path("/p"), "linux", True, which={"python3": "/usr/bin/python3"}.get, exists=lambda x: False) == "/usr/bin/python3"

    def test_frozen_without_any_python(self):
        assert od.find_python(Path("/p"), "win32", True, which=lambda n: None, exists=lambda x: False) is None

    def test_missing_python_or_flask_are_reported(self):
        monkeypatch_free = od.check_environment(ROOT, python="")
        assert any("Flask" in p for p in monkeypatch_free)
        assert any("Flask" in p for p in od.check_environment(ROOT, python="/no/existe/python"))

    def test_say_does_not_crash_without_console(self, monkeypatch):
        monkeypatch.setattr(sys, "stdout", None)
        od.say("hola")                                  # no debe lanzar
        monkeypatch.setattr(od, "FROZEN", True)
        monkeypatch.setattr(sys, "platform", "linux")
        od.notify("mensaje")                            # sin consola y sin Windows: se ignora sin fallar

    def test_build_script_and_icon_are_in_place(self):
        bat = (ROOT / "construir_exe.bat").read_text(encoding="utf-8")
        assert "--onefile" in bat and "--noconsole" in bat and "assets\\omnia.ico" in bat and "scripts\\omnia_desktop.py" in bat
        assert (ROOT / "assets" / "omnia.ico").read_bytes()[:4] == b"\x00\x00\x01\x00"
