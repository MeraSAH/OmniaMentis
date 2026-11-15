# tests/unit/test_ecosystem_store.py
"""
* UBICACIÓN: OmniaMentis/tests/unit/test_ecosystem_store.py
* PROPÓSITO: Tests del almacén único de datos de módulos
*            (src/core/storage/ecosystem_store.py) sobre la MISMA base que
*            las cuentas: aislamiento por cuenta, borrado en cascada,
*            exportación y límites.
* CREADO: 2026-10-17
* ESTADO: Test Permanente
"""

import sqlite3
import sys
import threading
import uuid
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from core.auth.accounts import AccountStore
from core.storage.ecosystem_store import (
    AccountMissing,
    EcosystemStore,
    InvalidRecord,
    StoreFull,
)

GOOD_PW = "una-clave-larga-123"


@pytest.fixture
def accounts(tmp_path):
    s = AccountStore(tmp_path / "accounts.db", pbkdf2_iterations=1000,
                     today=lambda: date(2026, 10, 10))
    yield s
    s.close()


@pytest.fixture
def eco(accounts, tmp_path):
    e = EcosystemStore(tmp_path / "accounts.db")
    yield e
    e.close()


def make_account(accounts, email="ana@example.com"):
    profile, _ = accounts.register(str(uuid.uuid4()), email, GOOD_PW, "1990-05-20")
    return profile["user_id"]


class TestSetup:
    def test_requires_accounts_table(self, tmp_path):
        sqlite3.connect(tmp_path / "vacia.db").close()
        with pytest.raises(RuntimeError):
            EcosystemStore(tmp_path / "vacia.db")

    def test_same_database_file_as_accounts(self, accounts, eco, tmp_path):
        conn = sqlite3.connect(tmp_path / "accounts.db")
        names = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        conn.close()
        assert {"accounts", "module_records"} <= names

    def test_reopening_is_idempotent(self, accounts, tmp_path):
        EcosystemStore(tmp_path / "accounts.db").close()
        EcosystemStore(tmp_path / "accounts.db").close()


class TestAddAndRead:
    def test_roundtrip(self, accounts, eco):
        a = make_account(accounts)
        rid = eco.add(a, "NutriVida", "imc", {"peso": 70.5, "altura": 1.75, "nota": "ñandú"})
        assert isinstance(rid, int)
        rows = eco.list(a, "NutriVida")
        assert len(rows) == 1
        assert rows[0]["payload"] == {"peso": 70.5, "altura": 1.75, "nota": "ñandú"}
        assert rows[0]["kind"] == "imc" and rows[0]["module"] == "NutriVida"

    def test_newest_first_and_latest(self, accounts, eco):
        a = make_account(accounts)
        for v in (1, 2, 3):
            eco.add(a, "OmniaHabits", "check", {"v": v})
        assert [r["payload"]["v"] for r in eco.list(a, "OmniaHabits")] == [3, 2, 1]
        assert eco.latest(a, "OmniaHabits", "check")["payload"]["v"] == 3
        assert eco.latest(a, "OmniaHabits", "otro") is None

    def test_kind_filter_and_limit(self, accounts, eco):
        a = make_account(accounts)
        for i in range(5):
            eco.add(a, "NutriVida", "agua", {"i": i})
        eco.add(a, "NutriVida", "imc", {"x": 1})
        assert len(eco.list(a, "NutriVida", "agua")) == 5
        assert len(eco.list(a, "NutriVida", "agua", limit=2)) == 2
        assert len(eco.list(a, "NutriVida")) == 6

    def test_accounts_are_isolated(self, accounts, eco):
        a = make_account(accounts, "a@example.com")
        b = make_account(accounts, "b@example.com")
        eco.add(a, "NutriVida", "imc", {"dueno": "a"})
        assert eco.list(b, "NutriVida") == []
        assert eco.count(b) == 0
        assert eco.export(b) == []

    def test_unknown_account_rejected_by_foreign_key(self, eco):
        with pytest.raises(AccountMissing):
            eco.add(str(uuid.uuid4()), "NutriVida", "imc", {"x": 1})

    def test_list_limit_is_capped(self, accounts, eco):
        a = make_account(accounts)
        eco.add(a, "NutriVida", "imc", {"x": 1})
        assert len(eco.list(a, "NutriVida", limit=10**9)) == 1


class TestValidation:
    @pytest.mark.parametrize("module", ["", "x", "1abc", "con/barra", "a" * 41, None, 5, "a;drop"])
    def test_bad_module(self, accounts, eco, module):
        a = make_account(accounts)
        with pytest.raises(InvalidRecord):
            eco.add(a, module, "imc", {"x": 1})

    @pytest.mark.parametrize("kind", ["", "A", "1x", "con espacio", "a" * 41, None, 7, "x'--"])
    def test_bad_kind(self, accounts, eco, kind):
        a = make_account(accounts)
        with pytest.raises(InvalidRecord):
            eco.add(a, "NutriVida", kind, {"x": 1})

    @pytest.mark.parametrize("payload", [None, [], "texto", 5, {"x": float("nan")},
                                         {"x": float("inf")}, {"x": object()}, {1, 2}])
    def test_bad_payload(self, accounts, eco, payload):
        a = make_account(accounts)
        with pytest.raises(InvalidRecord):
            eco.add(a, "NutriVida", "imc", payload)

    def test_payload_size_limit(self, accounts, tmp_path):
        e = EcosystemStore(tmp_path / "accounts.db", max_payload_bytes=100)
        a = make_account(accounts)
        e.add(a, "NutriVida", "imc", {"x": "a" * 50})
        with pytest.raises(InvalidRecord):
            e.add(a, "NutriVida", "imc", {"x": "a" * 200})
        e.close()

    def test_size_is_measured_in_bytes_not_chars(self, accounts, tmp_path):
        e = EcosystemStore(tmp_path / "accounts.db", max_payload_bytes=100)
        a = make_account(accounts)
        with pytest.raises(InvalidRecord):
            e.add(a, "NutriVida", "imc", {"x": "ñ" * 60})  # 60 chars, 120 bytes
        e.close()

    @pytest.mark.parametrize("limit", [0, -1, "5", None, True, 1.5])
    def test_bad_limit(self, accounts, eco, limit):
        a = make_account(accounts)
        with pytest.raises(InvalidRecord):
            eco.list(a, "NutriVida", limit=limit)

    def test_sql_injection_in_names_is_rejected_not_executed(self, accounts, eco):
        a = make_account(accounts)
        with pytest.raises(InvalidRecord):
            eco.list(a, "x'; DROP TABLE module_records;--")
        eco.add(a, "NutriVida", "imc", {"x": 1})
        assert eco.count(a) == 1

    @pytest.mark.parametrize("aid", ["", None, 5, "a" * 65])
    def test_bad_account_id(self, eco, aid):
        with pytest.raises(AccountMissing):
            eco.add(aid, "NutriVida", "imc", {"x": 1})


class TestLimitsAndDeletion:
    def test_per_account_cap(self, accounts, tmp_path):
        e = EcosystemStore(tmp_path / "accounts.db", max_records_per_account=3)
        a = make_account(accounts, "a@example.com")
        b = make_account(accounts, "b@example.com")
        for i in range(3):
            e.add(a, "NutriVida", "agua", {"i": i})
        with pytest.raises(StoreFull):
            e.add(a, "NutriVida", "agua", {"i": 99})
        e.add(b, "NutriVida", "agua", {"i": 1})  # el tope es por cuenta
        assert e.count(a) == 3
        e.close()

    def test_delete_module_only_touches_that_module_and_account(self, accounts, eco):
        a = make_account(accounts, "a@example.com")
        b = make_account(accounts, "b@example.com")
        eco.add(a, "NutriVida", "imc", {"x": 1})
        eco.add(a, "NutriVida", "imc", {"x": 2})
        eco.add(a, "OmniaHabits", "check", {"x": 3})
        eco.add(b, "NutriVida", "imc", {"x": 4})
        assert eco.delete_module(a, "NutriVida") == 2
        assert eco.count(a) == 1
        assert eco.count(b) == 1
        assert eco.delete_module(a, "NutriVida") == 0

    def test_deleting_the_account_deletes_all_module_data(self, accounts, eco):
        a = make_account(accounts, "a@example.com")
        b = make_account(accounts, "b@example.com")
        eco.add(a, "NutriVida", "imc", {"x": 1})
        eco.add(a, "OmniaHabits", "check", {"x": 2})
        eco.add(b, "NutriVida", "imc", {"x": 3})
        assert accounts.delete_account(a, GOOD_PW) is True
        assert eco.count(a) == 0
        assert eco.export(a) == []
        assert eco.count(b) == 1

    def test_unconfirmed_guardian_account_removal_cascades(self, accounts, eco):
        a = make_account(accounts)
        eco.add(a, "NutriVida", "imc", {"x": 1})
        # abort_pending solo borra cuentas pendientes: una adulta no se toca
        assert accounts.abort_pending(a) is False
        assert eco.count(a) == 1


class TestExport:
    def test_export_is_chronological_and_complete(self, accounts, eco):
        a = make_account(accounts)
        eco.add(a, "NutriVida", "imc", {"n": 1})
        eco.add(a, "OmniaHabits", "check", {"n": 2})
        eco.add(a, "OmniaChronos", "bloque", {"n": 3})
        out = eco.export(a)
        assert [r["payload"]["n"] for r in out] == [1, 2, 3]
        assert {r["module"] for r in out} == {"NutriVida", "OmniaHabits", "OmniaChronos"}


class TestConcurrency:
    def test_parallel_writes_are_not_lost(self, accounts, eco):
        a = make_account(accounts)
        errors = []

        def worker(k):
            try:
                for i in range(20):
                    eco.add(a, "OmniaHabits", "check", {"k": k, "i": i})
            except Exception as exc:  # pragma: no cover
                errors.append(exc)

        threads = [threading.Thread(target=worker, args=(k,)) for k in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert errors == []
        assert eco.count(a) == 100

    def test_writes_visible_from_a_second_connection(self, accounts, eco, tmp_path):
        a = make_account(accounts)
        eco.add(a, "NutriVida", "imc", {"x": 1})
        other = EcosystemStore(tmp_path / "accounts.db")
        assert other.count(a) == 1
        other.close()


class TestCounts:
    def test_counts_per_module_and_isolated_by_account(self, tmp_path):
        import sys, uuid
        from datetime import date
        from core.auth.accounts import AccountStore
        from core.storage.ecosystem_store import EcosystemStore
        accounts = AccountStore(tmp_path / "a.db", pbkdf2_iterations=1000, today=lambda: date(2026, 10, 10))
        store = EcosystemStore(tmp_path / "a.db")
        a, _ = accounts.register(str(uuid.uuid4()), "a@example.com", "una-clave-larga-123", "1990-05-20")
        b, _ = accounts.register(str(uuid.uuid4()), "b@example.com", "una-clave-larga-123", "1990-05-21")
        store.add(a["user_id"], "NutriVida", "calculo", {"x": 1})
        store.add(a["user_id"], "NutriVida", "calculo", {"x": 2})
        store.add(a["user_id"], "OmniaHabits", "habit_check", {"h": 1})
        store.add(b["user_id"], "NutriVida", "calculo", {"x": 3})
        assert store.counts(a["user_id"]) == {"NutriVida": 2, "OmniaHabits": 1}
        assert store.counts(b["user_id"]) == {"NutriVida": 1}
        assert store.counts("nadie") == {}
        with pytest.raises(AccountMissing):
            store.counts("")
        store.close(); accounts.close()
