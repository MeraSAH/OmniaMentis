# tests/unit/test_engine_business.py
"""
* UBICACIÓN: OmniaMentis/tests/unit/test_engine_business.py
* PROPÓSITO: Tests del motor de negocio (src/core/business/business.py) y del módulo
*            OmniaEngine con el almacén único REAL. Las cifras esperadas están
*            calculadas a mano (no copiadas de la salida del código).
* CREADO: 2026-10-20
* ESTADO: Test Permanente
"""

import sys
import uuid
from datetime import date
from decimal import Decimal as D
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from core.auth.accounts import AccountStore
from core.business import business as biz
from core.storage.ecosystem_store import EcosystemStore
from router.keyword_router import KeywordRouter
from router.modules.base_module import OmniaContext
from router.modules.omnia_engine import OmniaEngineModule


class TestMoney:
    @pytest.mark.parametrize("text,expected", [("10", D("10")), ("10,50", D("10.50")), ("10.50", D("10.50")),
                                               ("1.200,50", D("1200.50")), ("1,200.50", D("1200.50")), ("0", D("0"))])
    def test_dec(self, text, expected):
        assert biz._dec(text) == expected

    @pytest.mark.parametrize("bad", ["", "abc", "NaN", "Infinity", "1.2.3,4,5x"])
    def test_dec_rejects(self, bad):
        with pytest.raises(biz.InvalidInput):
            biz._dec(bad)

    def test_rounding_is_half_up_not_bankers(self):
        assert biz.money(D("0.125")) == D("0.13") and biz.money(D("0.135")) == D("0.14") and biz.money(D("2.675")) == D("2.68")

    def test_fmt_money(self):
        assert biz.fmt_money(D("1234567.891")) == "$1,234,567.89"


class TestParseItems:
    def test_semicolon_format_with_qty_and_decimal_comma(self):
        items, ign = biz.parse_items("cotiza: diseño web: 1 x 500; hosting anual: 12 x 10,50; logo: 120")
        assert ign == [] and [(i["name"], i["qty"], i["unit_price"]) for i in items] == [
            ("diseño web", D(1), D(500)), ("hosting anual", D(12), D("10.50")), ("logo", D(1), D(120))]

    def test_comma_space_separated_without_colons(self):
        items, ign = biz.parse_items("quiero una cotización de diseño web 500, hosting 120, logo 3 x 40")
        assert ign == [] and [(i["name"], i["qty"], i["unit_price"]) for i in items] == [
            ("diseño web", D(1), D(500)), ("hosting", D(1), D(120)), ("logo", D(3), D(40))]

    def test_percent_phrases_are_not_taken_as_items(self):
        items, ign = biz.parse_items("cotiza: logo: 100 descuento 10% iva 12%")
        assert len(items) == 1 and ign == []

    def test_unrecognized_parts_are_reported_not_dropped_silently(self):
        items, ign = biz.parse_items("cotización proyecto web: diseño 500; hosting 120")
        assert [i["name"] for i in items] == ["hosting"] and ign == ["proyecto web: diseño 500"]

    @pytest.mark.parametrize("text", ["cotiza", "presupuesto", "", None])
    def test_nothing_to_parse(self, text):
        assert biz.parse_items(text) == ([], [])

    def test_long_names_are_truncated(self):
        items, _ = biz.parse_items("cotiza: " + "a" * 200 + ": 5")
        assert len(items[0]["name"]) == biz.MAX_NAME


class TestQuote:
    def test_hand_computed_quote(self):
        # 500 + 12*10.50 + 120 = 746.00 ; -10% = 74.60 ; base 671.40 ; IVA 15% = 100.71 ; total 772.11
        items = [{"name": "a", "qty": D(1), "unit_price": D(500)}, {"name": "b", "qty": D(12), "unit_price": D("10.50")},
                 {"name": "c", "qty": D(1), "unit_price": D(120)}]
        q = biz.build_quote(items, D(15), D(10))
        assert (q["subtotal"], q["discount"], q["base"], q["vat"], q["total"]) == (
            D("746.00"), D("74.60"), D("671.40"), D("100.71"), D("772.11"))

    def test_no_discount_no_vat(self):
        q = biz.build_quote([{"name": "a", "qty": D(3), "unit_price": D("19.99")}], D(0), D(0))
        assert q["total"] == D("59.97") and q["vat"] == D("0.00")

    def test_line_rounding_happens_per_line(self):
        q = biz.build_quote([{"name": "a", "qty": D("0.5"), "unit_price": D("0.05")}], D(0))   # 0.025 -> 0.03
        assert q["lines"][0]["total"] == D("0.03")

    @pytest.mark.parametrize("items", [
        [], [{"name": "a", "qty": D(0), "unit_price": D(1)}], [{"name": "a", "qty": D(-1), "unit_price": D(1)}],
        [{"name": "a", "qty": D(1), "unit_price": D(-5)}], [{"name": "a", "qty": D(2_000_000), "unit_price": D(1)}],
        [{"name": "a", "qty": D(1_000_000), "unit_price": D(1_000_000)}], [{"name": "a", "qty": D(1), "unit_price": D(2_000_000_000)}]])
    def test_invalid_items(self, items):
        with pytest.raises(biz.InvalidInput):
            biz.build_quote(items)

    def test_too_many_items_and_bad_percentages(self):
        one = {"name": "a", "qty": D(1), "unit_price": D(1)}
        with pytest.raises(biz.InvalidInput):
            biz.build_quote([one] * (biz.MAX_ITEMS + 1))
        assert biz.build_quote([one] * biz.MAX_ITEMS)["subtotal"] == D(50)
        for vat, disc in [(D(101), D(0)), (D(-1), D(0)), (D(15), D(100.5)), (D(15), D(-1))]:
            with pytest.raises(biz.InvalidInput):
                biz.build_quote([one], vat, disc)

    def test_percent_parsing(self):
        assert biz.parse_percent(biz._VAT, "iva 12%", D(15)) == D(12)
        assert biz.parse_percent(biz._VAT, "IVA del 8,5 %", D(15)) == D("8.5")
        assert biz.parse_percent(biz._VAT, "sin iva mencionado", D(15)) == D(15)
        assert biz.parse_percent(biz._DISCOUNT, "descuento 10%", D(0)) == D(10)
        with pytest.raises(biz.InvalidInput):
            biz.parse_percent(biz._DISCOUNT, "descuento 150%", D(0))

    def test_summary_is_json_safe(self):
        import json
        q = biz.build_quote([{"name": "a", "qty": D(2), "unit_price": D("10.5")}], D(15))
        assert json.loads(json.dumps(biz.quote_summary(q)))["total"] == 24.15


class TestFunnel:
    def test_parse_stages_and_meta(self):
        f = biz.parse_funnel("embudo: visitas 1000, leads 100, clientes 10, inversión 500, ticket 80")
        assert [(s["name"], s["count"]) for s in f["stages"]] == [("visitas", D(1000)), ("leads", D(100)), ("clientes", D(10))]
        assert f["meta"] == {"investment": D(500), "ticket": D(80)}

    def test_hand_computed_analysis(self):
        # 1000 -> 200 (20 %) -> 50 (25 %) -> 10 (20 %). Peor paso: 20 % (el primero). CAC = 600/10 = 60.
        # Ingresos = 10*150 = 1500 ; ROI = (1500-600)/600 = 150 %
        stages = [{"name": n, "count": D(c)} for n, c in [("visitas", 1000), ("leads", 200), ("citas", 50), ("clientes", 10)]]
        r = biz.analyze_funnel(stages, D(600), D(150))
        assert [x["from_previous_pct"] for x in r["stages"]] == [None, D("20.0"), D("25.0"), D("20.0")]
        assert [x["from_start_pct"] for x in r["stages"]] == [D("100.0"), D("20.0"), D("5.0"), D("1.0")]
        assert r["worst_step"] == {"from": "visitas", "to": "leads", "pct": D("20.0")}
        assert r["cac"] == D("60.00") and r["revenue"] == D("1500.00") and r["roi_pct"] == D("150.0")

    def test_growing_stage_warns_and_is_not_fixed(self):
        r = biz.analyze_funnel([{"name": "a", "count": D(10)}, {"name": "b", "count": D(20)}])
        assert r["warnings"] and r["stages"][1]["from_previous_pct"] == D("200.0") and r["worst_step"] is None

    def test_zero_counts_do_not_divide_by_zero(self):
        r = biz.analyze_funnel([{"name": "a", "count": D(0)}, {"name": "b", "count": D(0)}], D(100), D(10))
        assert r["stages"][0]["from_start_pct"] is None and "cac" not in r and r["revenue"] == D("0.00")

    def test_no_investment_means_no_cac_or_roi(self):
        r = biz.analyze_funnel([{"name": "a", "count": D(10)}, {"name": "b", "count": D(5)}], None, D(10))
        assert "cac" not in r and "roi_pct" not in r and r["revenue"] == D("50.00")

    @pytest.mark.parametrize("stages", [[], [{"name": "a", "count": D(1)}],
                                        [{"name": str(i), "count": D(1)} for i in range(9)],
                                        [{"name": "a", "count": D(-1)}, {"name": "b", "count": D(1)}]])
    def test_invalid_stage_lists(self, stages):
        with pytest.raises(biz.InvalidInput):
            biz.analyze_funnel(stages)

    def test_invalid_investment_or_ticket(self):
        s = [{"name": "a", "count": D(1)}, {"name": "b", "count": D(1)}]
        with pytest.raises(biz.InvalidInput):
            biz.analyze_funnel(s, D(-1))
        with pytest.raises(biz.InvalidInput):
            biz.analyze_funnel(s, None, D(-1))

    def test_format_mentions_biggest_drop(self):
        s = [{"name": "visitas", "count": D(1000)}, {"name": "leads", "count": D(100)}]
        assert "Mayor caída: de «visitas» a «leads»" in biz.format_funnel(biz.analyze_funnel(s))


@pytest.fixture
def env(tmp_path):
    accounts = AccountStore(tmp_path / "a.db", pbkdf2_iterations=1000, today=lambda: date(2026, 10, 10))
    store = EcosystemStore(tmp_path / "a.db")
    p, _ = accounts.register(str(uuid.uuid4()), "ana@example.com", "una-clave-larga-123", "1990-05-20")
    ctx = OmniaContext(user_id=p["user_id"], consciousness_level=0.1, session_id="s", age_band="adult", data_store=store)
    yield OmniaEngineModule(), ctx, store
    store.close()
    accounts.close()


class TestModule:
    def test_menu_is_honest_about_unimplemented_parts(self, env):
        m, ctx, _ = env
        r = m.handle("quiero automatizar mi negocio con un crm", ctx)
        assert r.data["status"] == "menu" and "todavía no existen" in r.text

    def test_quote_declares_assumed_vat_and_saves(self, env):
        m, ctx, store = env
        r = m.handle("cotiza: diseño web: 1 x 500; hosting: 12 x 10,50; logo: 120 descuento 10%", ctx)
        assert r.data["status"] == "quoted" and r.data["total"] == 772.11 and r.data["saved"] is True
        assert "Supuse IVA 15" in r.text and "TOTAL: $772.11" in r.text
        rec = store.list(ctx.user_id, "OmniaEngine", "cotizacion")[0]["payload"]
        assert rec["total"] == 772.11 and len(rec["lines"]) == 3

    def test_explicit_vat_is_not_called_an_assumption(self, env):
        m, ctx, _ = env
        r = m.handle("cotiza: logo: 100 iva 12%", ctx)
        assert "Supuse" not in r.text and "IVA (12 %): $12.00" in r.text and "TOTAL: $112.00" in r.text

    def test_ignored_parts_are_listed_and_followup_is_requested(self, env):
        m, ctx, _ = env
        r = m.handle("cotización proyecto web: diseño 500; hosting 120", ctx)
        assert "NO las incluí" in r.text and r.requires_followup is True and r.data["total"] == 138.0

    def test_quote_without_items_asks_for_format(self, env):
        m, ctx, store = env
        r = m.handle("necesito una cotización", ctx)
        assert r.data["status"] == "needs_items" and store.count(ctx.user_id) == 0

    @pytest.mark.parametrize("msg", ["cotiza: logo: 100 descuento 150%", "cotiza: logo: 0 x 100",
                                     "cotiza: logo: 5000000000"])
    def test_invalid_quote_is_explained_and_not_saved(self, env, msg):
        m, ctx, store = env
        r = m.handle(msg, ctx)
        assert r.data["status"] == "invalid_input" and store.count(ctx.user_id) == 0

    def test_funnel_saved_and_computed(self, env):
        m, ctx, store = env
        r = m.handle("embudo: visitas 1000, leads 100, clientes 10, inversión 500, ticket 80", ctx)
        assert r.data["status"] == "funnel" and r.data["saved"] is True
        assert "CAC" in r.text and "$50.00" in r.text and "60.0 %" in r.text
        assert store.list(ctx.user_id, "OmniaEngine", "embudo")[0]["payload"]["cac"] == 50.0

    def test_funnel_with_too_few_stages(self, env):
        m, ctx, store = env
        assert m.handle("embudo: visitas 1000", ctx).data["status"] == "invalid_input"
        assert store.count(ctx.user_id) == 0

    def test_works_without_store(self, env):
        m, ctx, _ = env
        ctx.data_store = None
        assert m.handle("cotiza: logo: 100", ctx).data["saved"] is False

    def test_store_failure_does_not_break_the_answer(self, env):
        m, ctx, _ = env

        class Broken:
            def add(self, *a, **k):
                raise RuntimeError("boom")
        ctx.data_store = Broken()
        r = m.handle("cotiza: logo: 100", ctx)
        assert r.data["status"] == "quoted" and r.data["saved"] is False


class TestRouting:
    @pytest.mark.parametrize("msg", ["cotiza: logo: 100", "embudo: visitas 1000, leads 100", "quiero una cotización de un proyecto"])
    def test_routes_to_engine_for_adults(self, msg):
        r = KeywordRouter().route(msg, OmniaContext("u", 0.1, "s", age_band="adult"))
        assert r.module_response.module_name == "OmniaEngine"

    @pytest.mark.parametrize("band", ["minor", "minor_basic"])
    def test_minors_are_restricted(self, band):
        r = KeywordRouter().route("cotiza: logo: 100", OmniaContext("u", 0.1, "s", age_band=band))
        assert r.age_restricted_module == "OmniaEngine" and r.module_response is None
