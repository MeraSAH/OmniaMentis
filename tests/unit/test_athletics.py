# tests/unit/test_athletics.py
"""
* UBICACIÓN: OmniaMentis/tests/unit/test_athletics.py
* PROPÓSITO: Tests del motor de entrenamiento (src/core/fitness/training.py) y
*            del módulo OmniaAthletics con el almacén único REAL.
* CREADO: 2026-10-18
* ESTADO: Test Permanente
"""

import sys
import time
import uuid
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from core.auth.accounts import AccountStore
from core.fitness import training as tr
from core.storage.ecosystem_store import EcosystemStore
from router.keyword_router import KeywordRouter
from router.modules.base_module import OmniaContext
from router.modules.omnia_athletics import OmniaAthleticsModule

NOW = 1_800_000_000.0


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
    clock = Clock(time.time())   # el almacén sella created_at con la hora real

    def make(band="adult"):
        return OmniaContext(user_id=p["user_id"], consciousness_level=0.1, session_id="s",
                            age_band=band, data_store=store)
    yield OmniaAthleticsModule(clock=clock), make, clock, store, p["user_id"]
    store.close()
    accounts.close()


class TestEngineParsing:
    @pytest.mark.parametrize("msg,expected", [
        ("rutina de 4 días para masa en el gimnasio nivel intermedio",
         {"days": 4, "level": "intermedio", "goal": "masa", "place": "gimnasio"}),
        ("quiero entrenar 3 veces por semana en casa, soy principiante", {"days": 3, "level": "principiante", "place": "casa"}),
        ("rutina sin pesas de fuerza", {"goal": "fuerza", "place": "casa"}),
        ("rutina con mancuernas", {"place": "gimnasio"}),
        ("rutina", {}), ("", {}), (None, {})])
    def test_parse_request(self, msg, expected):
        assert tr.parse_request(msg) == expected

    @pytest.mark.parametrize("msg,expected", [
        ("entrené 45 minutos", 45.0), ("entrené 1.5 horas", 90.0), ("hice ejercicio 2 h", 120.0),
        ("entrené", None), ("", None), (None, None)])
    def test_parse_minutes(self, msg, expected):
        assert tr.parse_minutes(msg) == expected

    @pytest.mark.parametrize("m,ok", [(4, False), (5, True), (300, True), (301, False), (0, False), (-5, False),
                                      ("45", False), (None, False), (True, False)])
    def test_valid_minutes(self, m, ok):
        assert tr.valid_minutes(m) is ok

    @pytest.mark.parametrize("msg,expected", [
        ("quiero bajar de peso", True), ("rutina para definición", True), ("quemar grasa", True),
        ("rutina de fuerza", False), ("", False), (None, False)])
    def test_wants_fat_loss(self, msg, expected):
        assert tr.wants_fat_loss(msg) is expected


class TestEngineRoutine:
    def test_defaults_are_declared(self):
        r = tr.build_routine("adult")
        assert (r["days"], r["level"], r["goal"], r["place"]) == (3, "principiante", "salud", "casa")
        assert len(r["assumed"]) == 4 and r["adjusted"] == []

    @pytest.mark.parametrize("days", [2, 3, 4, 5, 6])
    def test_sessions_match_days_and_have_exercises(self, days):
        r = tr.build_routine("adult", days=days, level="intermedio", goal="masa", place="gimnasio")
        assert len(r["sessions"]) == days and all(s["exercises"] for s in r["sessions"])

    @pytest.mark.parametrize("days", [0, 1, 7, 10, -1, True, "3", 3.0])
    def test_invalid_days(self, days):
        with pytest.raises(tr.InvalidRequest):
            tr.build_routine("adult", days=days)

    @pytest.mark.parametrize("kw", [{"level": "pro"}, {"goal": "bajar"}, {"place": "luna"}])
    def test_invalid_options(self, kw):
        with pytest.raises(tr.InvalidRequest):
            tr.build_routine("adult", days=3, **kw)

    def test_adult_strength_advanced(self):
        r = tr.build_routine("adult", days=4, level="avanzado", goal="fuerza", place="gimnasio")
        ex = r["sessions"][0]["exercises"][0]
        assert (ex["sets"], ex["reps"], ex["rest_s"]) == (5, "3-6", 180)

    @pytest.mark.parametrize("band", ["minor", "minor_basic", ""])
    def test_non_adults_get_safe_limits(self, band):
        r = tr.build_routine(band, days=6, level="avanzado", goal="fuerza", place="gimnasio")
        assert r["days"] == 4 and r["level"] == "intermedio" and r["minor"] is True
        assert len(r["adjusted"]) == 3
        for s in r["sessions"]:
            for e in s["exercises"]:
                assert e["sets"] <= 3 and e["rest_s"] <= 90
                if e["reps"].replace("-", "").isdigit():
                    assert int(e["reps"].split("-")[0]) >= 8

    @pytest.mark.parametrize("goal", ["salud", "fuerza", "masa", "resistencia"])
    @pytest.mark.parametrize("level", ["principiante", "intermedio", "avanzado"])
    def test_minor_never_below_8_reps_for_any_combo(self, goal, level):
        r = tr.build_routine("minor_basic", days=4, level=level, goal=goal, place="casa")
        for s in r["sessions"]:
            for e in s["exercises"]:
                if e["sets"] > 1 and e["reps"].replace("-", "").isdigit():
                    assert int(e["reps"].split("-")[0]) >= 8 and e["sets"] <= 3

    def test_endurance_alternates_cardio(self):
        r = tr.build_routine("adult", days=4, goal="resistencia")
        names = [s["name"] for s in r["sessions"]]
        assert names[0] == "Cardio en zona 2" and names[2] == "Cardio en zona 2" and len(r["sessions"]) == 4

    def test_home_and_gym_use_different_exercises(self):
        a = tr.build_routine("adult", days=2, place="casa")
        b = tr.build_routine("adult", days=2, place="gimnasio")
        assert a["sessions"][0]["exercises"][0]["name"] != b["sessions"][0]["exercises"][0]["name"]

    def test_notes_mention_supervision_only_for_minors(self):
        assert any("supervisión" in n for n in tr.routine_notes(True))
        assert not any("supervisión" in n for n in tr.routine_notes(False))
        assert any("no una valoración médica" in n for n in tr.routine_notes(False))

    def test_format_routine_is_text(self):
        out = tr.format_routine(tr.build_routine("adult", days=2))
        assert "Día 1" in out and "Día 2" in out


class TestWeekSummary:
    def test_counts_only_last_7_days_and_ignores_broken(self):
        rows = [
            {"created_at": NOW - 100, "payload": {"minutes": 40}},
            {"created_at": NOW - 6 * 86400, "payload": {"minutes": 30}},
            {"created_at": NOW - 8 * 86400, "payload": {"minutes": 99}},
            {"created_at": NOW - 10, "payload": {"minutes": "x"}},
            {"created_at": NOW - 10, "payload": {}},
            {"payload": {"minutes": 10}},
            {"created_at": NOW - 10, "payload": {"minutes": 9999}},
            {"created_at": NOW + 99999, "payload": {"minutes": 20}},
        ]
        assert tr.summarize_week(rows, NOW) == {"sessions": 2, "minutes": 70.0}

    def test_empty_and_none(self):
        assert tr.summarize_week([], NOW) == {"sessions": 0, "minutes": 0.0}
        assert tr.summarize_week(None, NOW) == {"sessions": 0, "minutes": 0.0}


class TestModule:
    def test_routine_default_and_saved(self, env):
        m, make, _, store, uid = env
        r = m.handle("dame una rutina", make())
        assert r.data["status"] == "routine" and r.data["saved"] is True and r.requires_followup is True
        assert "Supuse" in r.text and "Día 3" in r.text
        assert store.list(uid, "OmniaAthletics", "rutina")[0]["payload"]["days"] == 3

    def test_routine_with_choices_has_no_assumption_text(self, env):
        m, make, _, _, _ = env
        r = m.handle("rutina de 4 días para masa en el gimnasio nivel intermedio", make())
        assert "Supuse" not in r.text and r.requires_followup is False and r.data["days"] == 4

    def test_invalid_days_asks_again(self, env):
        m, make, _, store, uid = env
        r = m.handle("rutina de 9 días", make())
        assert r.data["status"] == "invalid_request" and store.count(uid) == 0

    def test_minor_is_adjusted_and_told(self, env):
        m, make, _, _, _ = env
        r = m.handle("rutina de 6 días de fuerza nivel avanzado en el gimnasio", make("minor_basic"))
        assert r.data["days"] == 4 and "Ajusté por tu edad" in r.text and "supervisión" in r.text

    @pytest.mark.parametrize("msg", ["quiero bajar de peso con una rutina", "rutina para definición", "quiero adelgazar y entrenar"])
    def test_minor_fat_loss_is_redirected_and_nothing_saved(self, env, msg):
        m, make, _, store, uid = env
        r = m.handle(msg, make("minor_basic"))
        assert r.data["status"] == "minor_safe_redirect" and store.count(uid) == 0
        assert "Día 1" not in r.text

    def test_adult_fat_loss_gets_routine_with_nutrition_note(self, env):
        m, make, _, _, _ = env
        r = m.handle("quiero bajar de peso, dame una rutina", make("adult"))
        assert r.data["status"] == "routine" and "NutriVida" in r.text

    def test_log_workout_then_summary(self, env):
        m, make, clock, store, uid = env
        r = m.handle("entrené 45 minutos", make())
        assert r.data["status"] == "logged" and r.data["week"] == {"sessions": 1, "minutes": 45.0}
        clock.t += 86400
        m.handle("entrené 1 hora", make())
        s = m.handle("¿cuál es mi resumen de entrenamiento de esta semana?", make())
        assert s.data["status"] == "summary" and s.data["week"] == {"sessions": 2, "minutes": 105.0}
        assert "150 minutos" in s.text

    def test_week_window_moves(self, env):
        m, make, clock, _, _ = env
        m.handle("entrené 45 minutos", make())
        clock.t += 8 * 86400
        s = m.handle("mi progreso de entrenamiento", make())
        assert s.data["week"]["sessions"] == 0 and "No tienes entrenamientos" in s.text

    def test_minor_summary_uses_minor_reference(self, env):
        m, make, _, _, _ = env
        s = m.handle("mi progreso de entrenamiento", make("minor_basic"))
        assert "60 minutos" in s.text and "150" not in s.text

    def test_log_without_minutes_asks(self, env):
        m, make, _, store, uid = env
        r = m.handle("entrené hoy", make())
        assert r.data["status"] == "needs_minutes" and store.count(uid) == 0

    @pytest.mark.parametrize("msg", ["entrené 3 minutos", "entrené 400 minutos"])
    def test_log_invalid_minutes_not_saved(self, env, msg):
        m, make, _, store, uid = env
        r = m.handle(msg, make())
        assert r.data["status"] == "invalid_minutes" and store.count(uid) == 0

    def test_no_store_routine_still_works_but_log_does_not(self, env):
        m, make, _, _, _ = env
        ctx = make()
        ctx.data_store = None
        assert m.handle("rutina de 3 días", ctx).data["saved"] is False
        assert m.handle("entrené 30 minutos", ctx).data["status"] == "unavailable"
        assert m.handle("mi progreso de entrenamiento", ctx).data["status"] == "unavailable"

    def test_store_failure_is_reported_not_raised(self, env):
        m, make, _, _, _ = env
        ctx = make()

        class Broken:
            def add(self, *a, **k):
                raise RuntimeError("boom")

            def list(self, *a, **k):
                raise RuntimeError("boom")
        ctx.data_store = Broken()
        assert m.handle("entrené 30 minutos", ctx).data["status"] == "not_saved"
        assert m.handle("mi progreso de entrenamiento", ctx).data["status"] == "unavailable"
        assert m.handle("rutina", ctx).data["saved"] is False

    def test_each_account_has_its_own_week(self, env):
        m, make, _, store, uid = env
        m.handle("entrené 45 minutos", make())
        other = make()
        other.user_id = "otra-cuenta"
        assert m.handle("mi progreso de entrenamiento", other).data["week"]["sessions"] == 0
        assert m.handle("mi progreso de entrenamiento", make()).data["week"]["sessions"] == 1


class TestRouting:
    @pytest.mark.parametrize("msg", [
        "entrené 45 minutos", "dame una rutina de 4 días para masa en el gimnasio",
        "mi progreso de entrenamiento esta semana", "hice ejercicio 30 minutos"])
    def test_routes_to_athletics(self, msg):
        r = KeywordRouter().route(msg, OmniaContext("u", 0.1, "s", age_band="adult"))
        assert r.module_response.module_name == "OmniaAthletics"

    def test_habit_message_still_goes_to_habits(self):
        r = KeywordRouter().route("completé el entrenamiento de élite", OmniaContext("u", 0.1, "s", age_band="adult"))
        assert r.module_response.module_name == "OmniaHabits"

    def test_13_14_is_restricted_from_athletics(self):
        r = KeywordRouter().route("dame una rutina de gimnasio", OmniaContext("u", 0.1, "s", age_band="minor"))
        assert r.age_restricted_module == "OmniaAthletics" and r.module_response is None
