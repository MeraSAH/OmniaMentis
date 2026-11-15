# tests/unit/test_focus.py
"""
* UBICACIÓN: OmniaMentis/tests/unit/test_focus.py
* PROPÓSITO: Tests del motor de enfoque (src/core/focus/focus.py) y del módulo
*            OmniaChronos con el almacén único REAL.
* CREADO: 2026-10-18
* ESTADO: Test Permanente
"""

import sys
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from core.auth.accounts import AccountStore
from core.focus import focus as fc
from core.habits.habits import day_key
from core.storage.ecosystem_store import EcosystemStore
from router.keyword_router import KeywordRouter
from router.modules.base_module import OmniaContext
from router.modules.omnia_chronos import OmniaChronosModule

EC = timezone(timedelta(hours=-5))


def ts(y, m, d, h=10, mi=0):
    return datetime(y, m, d, h, mi, tzinfo=EC).timestamp()


class Clock:
    def __init__(self, t):
        self.t = t

    def __call__(self):
        return self.t


@pytest.fixture
def env(tmp_path):
    accounts = AccountStore(tmp_path / "a.db", pbkdf2_iterations=1000, today=lambda: date(2026, 10, 10))
    store = EcosystemStore(tmp_path / "a.db")
    p, _ = accounts.register(str(uuid.uuid4()), "ana@example.com", "una-clave-larga-123", "1990-05-20")
    clock = Clock(ts(2026, 10, 18))
    ctx = OmniaContext(user_id=p["user_id"], consciousness_level=0.1, session_id="s",
                       age_band="minor", data_store=store)
    yield OmniaChronosModule(clock=clock), ctx, clock, store
    store.close()
    accounts.close()


class TestEngine:
    @pytest.mark.parametrize("msg,expected", [
        ("bloque de enfoque de 45 minutos", 45), ("pomodoro 30 min", 30), ("90mins", 90),
        ("bloque de enfoque", None), ("", None), (None, None)])
    def test_parse_minutes(self, msg, expected):
        assert fc.parse_minutes(msg) == expected

    @pytest.mark.parametrize("m,ok", [(4, False), (5, True), (25, True), (180, True), (181, False), (0, False),
                                      (-3, False), ("25", False), (None, False), (True, False)])
    def test_valid_minutes(self, m, ok):
        assert fc.valid_minutes(m) is ok

    @pytest.mark.parametrize("msg,intent", [
        ("terminé el bloque", "end"), ("quiero cancelar el bloque de enfoque", "end"),
        ("¿cuánto he enfocado hoy?", "status"), ("bloque de enfoque de 25 minutos", "start"),
        ("iniciar pomodoro", "start")])
    def test_intent(self, msg, intent):
        assert fc.detect_intent(msg) == intent

    def test_label(self):
        assert fc.detect_label("bloque de enfoque de reset dopamínico") == "Reset Dopamínico"
        assert fc.detect_label("bloque para evolución cognitiva") == "Evolución Cognitiva"
        assert fc.detect_label("bloque de enfoque") is None

    def test_remaining_and_elapsed(self):
        assert fc.remaining_seconds(1000, 25, 1000 + 600) == 900
        assert fc.remaining_seconds(1000, 25, 1000 + 99999) == 0
        assert fc.elapsed_minutes(1000, 25, 1000 + 600) == 10.0
        assert fc.elapsed_minutes(1000, 25, 1000 + 99999) == 25.0   # nunca más de lo planeado
        assert fc.elapsed_minutes(1000, 25, 500) == 0.0              # reloj hacia atrás

    def test_summarize_day(self):
        a, b = ts(2026, 10, 18, 9), ts(2026, 10, 17, 9)
        out = fc.summarize_day([{"started_at": a, "elapsed_min": 25.0}, {"started_at": a, "elapsed_min": 10.5},
                                {"started_at": b, "elapsed_min": 99}, {"bad": 1}, {"started_at": "x", "elapsed_min": 1}],
                               "2026-10-18", day_key)
        assert out == {"minutes": 35.5, "blocks": 2}


class TestModule:
    def test_start_default_25(self, env):
        m, ctx, clock, store = env
        r = m.handle("quiero un bloque de enfoque", ctx)
        assert r.data["status"] == "started" and r.data["minutes"] == 25
        assert r.widget_type == "focus_timer"
        w = r.widget_payload
        assert w["ends_at"] == clock.t + 1500 and w["mode"] == "absolute_focus" and w["request_block_notifications"] is True
        assert store.count(ctx.user_id) == 1

    def test_start_custom_minutes_and_label(self, env):
        m, ctx, _, store = env
        r = m.handle("bloque de enfoque de 50 minutos de reset dopamínico", ctx)
        assert r.data["minutes"] == 50 and r.widget_payload["label"] == "Reset Dopamínico"
        assert store.list(ctx.user_id, "OmniaChronos", "focus_start")[0]["payload"]["label"] == "Reset Dopamínico"

    @pytest.mark.parametrize("msg", ["bloque de enfoque de 2 minutos", "bloque de enfoque de 500 minutos"])
    def test_invalid_minutes_not_saved(self, env, msg):
        m, ctx, _, store = env
        r = m.handle(msg, ctx)
        assert r.data["status"] == "invalid_minutes" and r.widget_type is None and store.count(ctx.user_id) == 0

    def test_cannot_start_second_block_while_running(self, env):
        m, ctx, clock, store = env
        m.handle("bloque de enfoque de 25 minutos", ctx)
        clock.t += 600
        r = m.handle("otro bloque de enfoque", ctx)
        assert r.data["status"] == "already_open" and r.data["remaining_seconds"] == 900
        assert store.count(ctx.user_id) == 1
        # el widget del bloque abierto se reenvía (la pantalla puede volver a abrirse)
        w = r.widget_payload
        assert r.widget_type == "focus_timer" and w["minutes"] == 25
        assert w["ends_at"] - w["server_now"] == 900 and w["ends_at"] - w["started_at"] == 1500

    def test_end_early_records_elapsed(self, env):
        m, ctx, clock, store = env
        m.handle("bloque de enfoque de 25 minutos", ctx)
        clock.t += 600
        r = m.handle("terminé el bloque", ctx)
        assert r.data["status"] == "ended" and r.data["elapsed_min"] == 10.0 and r.data["completed"] is False
        assert r.data["today"] == {"minutes": 10.0, "blocks": 1}
        assert "antes de tiempo" in r.text

    def test_end_after_time_is_completed_and_capped(self, env):
        m, ctx, clock, _ = env
        m.handle("bloque de enfoque de 25 minutos", ctx)
        clock.t += 3 * 3600  # se olvidó de cerrarlo
        r = m.handle("terminé el bloque", ctx)
        assert r.data["elapsed_min"] == 25.0 and r.data["completed"] is True

    def test_end_without_block(self, env):
        m, ctx, _, store = env
        r = m.handle("terminé el bloque de enfoque", ctx)
        assert r.data["status"] == "no_open_block" and store.count(ctx.user_id) == 0

    def test_end_is_not_applied_twice(self, env):
        m, ctx, clock, _ = env
        m.handle("bloque de enfoque de 25 minutos", ctx)
        clock.t += 300
        m.handle("terminé el bloque", ctx)
        assert m.handle("terminé el bloque", ctx).data["status"] == "no_open_block"

    def test_expired_unclosed_block_is_auto_closed_on_next_start(self, env):
        m, ctx, clock, store = env
        m.handle("bloque de enfoque de 25 minutos", ctx)
        clock.t += 7200
        r = m.handle("bloque de enfoque de 30 minutos", ctx)
        assert r.data["status"] == "started"
        ends = store.list(ctx.user_id, "OmniaChronos", "focus_end")
        assert len(ends) == 1 and ends[0]["payload"]["auto"] is True and ends[0]["payload"]["elapsed_min"] == 25.0

    def test_status_sums_today_only(self, env):
        m, ctx, clock, _ = env
        m.handle("bloque de enfoque de 25 minutos", ctx)
        clock.t += 1500
        m.handle("terminé el bloque", ctx)
        clock.t += 86400  # mañana
        r = m.handle("¿cuánto he enfocado hoy?", ctx)
        assert r.data["today"] == {"minutes": 0.0, "blocks": 0} and r.data["open"] is False

    def test_status_with_open_block(self, env):
        m, ctx, clock, _ = env
        m.handle("bloque de enfoque de 25 minutos", ctx)
        clock.t += 300
        r = m.handle("¿cómo va mi bloque actual?", ctx)
        assert r.data["open"] is True and "20 min" in r.text

    def test_users_are_isolated(self, env):
        m, ctx, _, store = env
        m.handle("bloque de enfoque de 25 minutos", ctx)
        other = OmniaContext(user_id="otra", consciousness_level=0.1, session_id="s", age_band="minor", data_store=store)
        assert m.handle("terminé el bloque", other).data["status"] == "no_open_block"

    def test_without_store(self, env):
        m, ctx, _, _ = env
        ctx.data_store = None
        r = m.handle("bloque de enfoque", ctx)
        assert r.data["status"] == "unavailable" and r.widget_type is None

    def test_store_failure_is_handled(self, env):
        m, ctx, _, _ = env

        class Broken:
            def list(self, *a, **k):
                raise RuntimeError("boom")

        ctx.data_store = Broken()
        assert m.handle("bloque de enfoque", ctx).data["status"] == "unavailable"

    def test_does_not_promise_to_block_device_notifications(self, env):
        m, ctx, _, _ = env
        text = m.handle("bloque de enfoque", ctx).text.lower()
        assert "bloque" in text and "bloqueo" not in text and "bloqueadas" not in text


class TestRouting:
    @pytest.mark.parametrize("msg", ["quiero un bloque de enfoque de 25 minutos", "iniciar pomodoro",
                                     "terminé el bloque de enfoque", "¿cuánto he enfocado? tiempo enfocado hoy"])
    def test_routes_to_chronos(self, msg):
        r = KeywordRouter().route(msg, OmniaContext("u", 0.1, "s", age_band="minor"))
        assert r.should_route and r.module_response.module_name == "OmniaChronos", r.scores
