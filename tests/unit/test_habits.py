# tests/unit/test_habits.py
"""
* UBICACIÓN: OmniaMentis/tests/unit/test_habits.py
* PROPÓSITO: Tests del motor de hábitos (src/core/habits/habits.py) y del módulo
*            OmniaHabits, con el almacén único REAL (SQLite en disco temporal).
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
from core.habits import habits as hb
from core.storage.ecosystem_store import EcosystemStore
from router.keyword_router import KeywordRouter
from router.modules.base_module import OmniaContext
from router.modules.omnia_habits import OmniaHabitsModule

EC = timezone(timedelta(hours=-5))


def ts(y, m, d, h=12, mi=0):
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
    profile, _ = accounts.register(str(uuid.uuid4()), "ana@example.com", "una-clave-larga-123", "1990-05-20")
    clock = Clock(ts(2026, 10, 18))
    module = OmniaHabitsModule(clock=clock)
    ctx = OmniaContext(user_id=profile["user_id"], consciousness_level=0.1, session_id="s",
                       age_band="adult", data_store=store)
    yield module, ctx, clock, store
    store.close()
    accounts.close()


class TestCatalog:
    def test_nine_habits_with_document_multipliers(self):
        m = {h["id"]: h["multiplier"] for h in hb.HABITS}
        assert len(m) == 9
        assert m["victoria_magistral"] == 3 and m["ducha_choque"] == 3
        assert m["entrenamiento_elite"] == 2 and m["reset_dopaminico"] == 2 and m["desintoxicacion_digital"] == 2
        for k in ("evolucion_cognitiva", "auditoria_tiempo", "estado_sobriedad", "bitacora_objetivos"):
            assert m[k] == 1

    def test_points_and_daily_max(self):
        assert hb.points_for("victoria_magistral") == 30
        assert hb.points_for("bitacora_objetivos") == 10
        assert hb.max_daily_points() == 160

    def test_ids_unique_and_hex_colors_valid(self):
        ids = [h["id"] for h in hb.HABITS]
        assert len(ids) == len(set(ids))
        for h in hb.HABITS:
            assert len(h["color_hex"]) == 7 and h["color_hex"].startswith("#")
            int(h["color_hex"][1:], 16)

    def test_document_colors(self):
        by = {h["id"]: h for h in hb.HABITS}
        assert by["victoria_magistral"]["color_name"] == "Rojo Carmesí"
        assert by["entrenamiento_elite"]["color_name"] == "Naranja Fuego"
        assert by["reset_dopaminico"]["color_name"] == "Morado Profundo"
        assert by["desintoxicacion_digital"]["color_name"] == "Amarillo Neón"


class TestParsing:
    @pytest.mark.parametrize("msg,hid", [
        ("Omnia, completé el Entrenamiento de Élite", "entrenamiento_elite"),
        ("COMPLETE EL ENTRENAMIENTO DE ELITE", "entrenamiento_elite"),
        ("hice la ducha fría", "ducha_choque"),
        ("cumplí la Victoria Magistral de las 6", "victoria_magistral"),
        ("marqué sobriedad", "estado_sobriedad"),
    ])
    def test_find_habit(self, msg, hid):
        assert hb.find_habit(msg)["id"] == hid

    def test_no_habit(self):
        assert hb.find_habit("hola") is None and hb.find_habit("") is None and hb.find_habit(None) is None

    def test_completion_and_status(self):
        assert hb.is_completion("completé algo")
        assert not hb.is_completion("quiero hacer ducha fría")  # "hacer" no es "hice"
        assert hb.is_status_request("¿cómo voy con mi racha?")
        assert not hb.is_status_request("hola")


class TestProgress:
    def test_matches_percentage_formula(self):
        p = hb.progress(["entrenamiento_elite", "evolucion_cognitiva"])  # 20 + 10
        assert p["obtained"] == 30 and p["possible"] == 160 and p["remaining"] == 130
        assert p["percent"] == 18.8 and p["done"] == 2 and p["total"] == 9

    def test_ignores_duplicates_and_unknown(self):
        assert hb.progress(["ducha_choque", "ducha_choque", "inventado", None])["obtained"] == 30

    def test_empty(self):
        assert hb.progress([])["obtained"] == 0 and hb.progress([])["percent"] == 0.0


class TestStreak:
    def test_consecutive(self):
        assert hb.streak(["2026-10-18", "2026-10-17", "2026-10-16"], "2026-10-18") == 3

    def test_today_empty_counts_from_yesterday(self):
        assert hb.streak(["2026-10-17", "2026-10-16"], "2026-10-18") == 2

    def test_gap_breaks(self):
        assert hb.streak(["2026-10-18", "2026-10-16"], "2026-10-18") == 1
        assert hb.streak(["2026-10-15"], "2026-10-18") == 0

    def test_duplicates_and_bad_values(self):
        assert hb.streak(["2026-10-18", "2026-10-18", "x", None, ""], "2026-10-18") == 1
        assert hb.streak([], "2026-10-18") == 0
        assert hb.streak(["2026-10-18"], "mal") == 0

    def test_month_boundary(self):
        assert hb.streak(["2026-11-01", "2026-10-31", "2026-10-30"], "2026-11-01") == 3


class TestDayKey:
    def test_uses_ecuador_time(self):
        # 2026-10-19 02:00 UTC = 2026-10-18 21:00 en Ecuador
        utc = datetime(2026, 10, 19, 2, 0, tzinfo=timezone.utc).timestamp()
        assert hb.day_key(utc) == "2026-10-18"

    def test_late_night_is_same_day(self):
        assert hb.day_key(ts(2026, 10, 18, 23, 59)) == "2026-10-18"
        assert hb.day_key(ts(2026, 10, 19, 0, 1)) == "2026-10-19"


class TestModule:
    def test_check_awards_points_color_and_widget(self, env):
        m, ctx, _, store = env
        r = m.handle("Omnia, completé el Entrenamiento de Élite", ctx)
        assert r.data["status"] == "checked" and r.data["points"] == 20
        assert r.widget_type == "aura_pulse"
        assert r.widget_payload["color_hex"] == "#FF4500" and r.widget_payload["points"] == 20
        assert r.data["progress"]["obtained"] == 20 and r.data["streak"] == 1
        assert "+20" in r.text
        rows = store.list(ctx.user_id, "OmniaHabits", "check")
        assert len(rows) == 1 and rows[0]["payload"] == {"habit": "entrenamiento_elite", "day": "2026-10-18", "points": 20}

    def test_second_check_same_day_does_not_duplicate(self, env):
        m, ctx, _, store = env
        m.handle("completé el entrenamiento de élite", ctx)
        r = m.handle("completé el entrenamiento de élite", ctx)
        assert r.data["status"] == "already_done" and r.widget_type is None
        assert r.data["progress"]["obtained"] == 20
        assert len(store.list(ctx.user_id, "OmniaHabits", "check")) == 1

    def test_next_day_counts_again_and_builds_streak(self, env):
        m, ctx, clock, _ = env
        m.handle("completé la ducha fría", ctx)
        clock.t = ts(2026, 10, 19)
        r = m.handle("completé la ducha fría", ctx)
        assert r.data["status"] == "checked" and r.data["streak"] == 2
        assert r.data["progress"]["obtained"] == 30  # solo lo de hoy

    def test_missing_a_day_resets_streak(self, env):
        m, ctx, clock, _ = env
        m.handle("completé la ducha fría", ctx)
        clock.t = ts(2026, 10, 21)
        r = m.handle("¿cómo va mi racha?", ctx)
        assert r.data["streak"] == 0

    def test_accumulates_points_across_habits(self, env):
        m, ctx, _, _ = env
        m.handle("completé la victoria magistral", ctx)
        r = m.handle("completé el estado de sobriedad", ctx)
        assert r.data["progress"]["obtained"] == 40 and r.data["progress"]["done"] == 2

    def test_users_are_isolated(self, env, tmp_path):
        m, ctx, _, store = env
        m.handle("completé la ducha fría", ctx)
        other = OmniaContext(user_id="otra-cuenta", consciousness_level=0.1, session_id="s",
                             age_band="adult", data_store=store)
        r = m.handle("¿cómo voy con mis puntos?", other)
        assert r.data["progress"]["obtained"] == 0

    def test_mention_without_completion_only_informs(self, env):
        m, ctx, _, store = env
        r = m.handle("háblame de la ducha de choque", ctx)
        assert r.data["status"] == "info" and "30 puntos" in r.text
        assert store.count(ctx.user_id) == 0

    def test_help_lists_catalog(self, env):
        m, ctx, _, _ = env
        r = m.handle("quiero crear un hábito", ctx)
        assert r.data["status"] == "help" and "Victoria Magistral 6:00 AM (×3)" in r.text

    def test_without_store_does_not_claim_to_save(self, env):
        m, ctx, _, _ = env
        ctx.data_store = None
        r = m.handle("completé la ducha fría", ctx)
        assert r.data["status"] == "unavailable" and "puntos" not in r.text.lower().replace("no se sumaron puntos", "")

    def test_store_write_failure_awards_nothing(self, env):
        m, ctx, _, store = env

        class Broken:
            def list(self, *a, **k):
                return []

            def add(self, *a, **k):
                raise RuntimeError("disco lleno")

        ctx.data_store = Broken()
        r = m.handle("completé la ducha fría", ctx)
        assert r.data["status"] == "not_saved" and r.widget_type is None

    def test_store_read_failure_is_handled(self, env):
        m, ctx, _, _ = env

        class Broken:
            def list(self, *a, **k):
                raise RuntimeError("boom")

        ctx.data_store = Broken()
        assert m.handle("completé la ducha fría", ctx).data["status"] == "unavailable"

    def test_full_day_reaches_100_percent(self, env):
        m, ctx, _, _ = env
        for h in hb.HABITS:
            r = m.handle(f"completé {h['aliases'][0]}", ctx)
        assert r.data["progress"]["percent"] == 100.0 and r.data["progress"]["remaining"] == 0


class TestRouting:
    @pytest.mark.parametrize("msg", [
        "Omnia, completé el Entrenamiento de Élite",
        "completé la victoria magistral",
        "completé la ducha de choque",
        "Quiero mantener mi racha de hábitos",
    ])
    def test_routes_to_habits(self, msg):
        r = KeywordRouter().route(msg, OmniaContext("u", 0.1, "s", age_band="adult"))
        assert r.should_route and r.module_response.module_name == "OmniaHabits", r.scores

    @pytest.mark.parametrize("msg", [
        "completé el reset dopamínico", "completé la desintoxicación digital",
        "completé la evolución cognitiva", "completé la auditoría de tiempo"])
    def test_catalog_habits_shared_with_chronos_go_to_habits(self, msg):
        r = KeywordRouter().route(msg, OmniaContext("u", 0.1, "s", age_band="adult"))
        assert r.module_response.module_name == "OmniaHabits", r.scores

    def test_focus_block_still_goes_to_chronos(self):
        r = KeywordRouter().route("quiero un bloque de enfoque de 25 minutos",
                                  OmniaContext("u", 0.1, "s", age_band="adult"))
        assert r.module_response.module_name == "OmniaChronos"
