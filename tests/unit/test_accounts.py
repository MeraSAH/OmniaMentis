# tests/unit/test_accounts.py
"""
* UBICACIÓN: OmniaMentis/tests/unit/test_accounts.py
* PROPÓSITO: Tests de src/core/auth/accounts.py (cuentas de usuario)
* DEPENDENCIAS: pytest
* CREADO: 2026-10-10
* ESTADO: Test Permanente
*
* Para que la suite sea rápida, el almacén se crea con 1 000 iteraciones
* de PBKDF2 (el mínimo que acepta el módulo). El valor real (600 000) se
* comprueba solo por su constante. El reloj y la fecha "de hoy" se
* inyectan: ningún test depende de la hora real.
"""

import sqlite3
import sys
import threading
import uuid
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from core.auth import accounts as acc
from core.auth.accounts import (
    AccountNotFound,
    AccountStore,
    EmailTaken,
    IdentityInUse,
    InvalidBirthDate,
    InvalidCredentials,
    InvalidDisplayName,
    InvalidEmail,
    UnderageError,
    WeakPassword,
)

TODAY = date(2026, 10, 10)
GOOD_PW = "una-clave-larga-123"
ADULT_BIRTH = "1990-05-20"


class FakeClock:
    def __init__(self, start=1_000_000.0):
        self.t = start

    def __call__(self):
        return self.t

    def advance(self, seconds):
        self.t += seconds


@pytest.fixture
def clock():
    return FakeClock()


@pytest.fixture
def store(tmp_path, clock):
    s = AccountStore(tmp_path / "accounts.db", pbkdf2_iterations=1000,
                     clock=clock, today=lambda: TODAY)
    yield s
    s.close()


def new_id():
    return str(uuid.uuid4())


def register(store, email="ana@example.com", password=GOOD_PW, birth=ADULT_BIRTH,
             name=None, user_id=None):
    return store.register(user_id or new_id(), email, password, birth, name)


# ── Constantes ───────────────────────────────────────────────────────────────

class TestConstants:
    def test_production_iterations_follow_owasp(self):
        assert acc.PBKDF2_ITERATIONS >= 600_000

    def test_minimum_age_is_13(self):
        assert acc.MIN_AGE == 13


# ── Email ────────────────────────────────────────────────────────────────────

class TestEmail:
    def test_normalizes_case_and_spaces(self):
        assert acc.normalize_email("  Ana@Example.COM ") == "ana@example.com"

    @pytest.mark.parametrize("bad", [
        "", "sin-arroba", "a@b", "@example.com", "ana@", "a b@example.com",
        "ana@exa mple.com", "ana..x@example.com", ".ana@example.com",
        "ana.@example.com", "ñandú@example.com", None, 123,
        "a" * 65 + "@example.com", "a@" + "b" * 250 + ".com",
    ])
    def test_rejects_invalid(self, bad):
        with pytest.raises(InvalidEmail):
            acc.normalize_email(bad)

    def test_accepts_plus_and_dots(self):
        assert acc.normalize_email("ana.perez+omnia@mail.example.org") == "ana.perez+omnia@mail.example.org"


# ── Contraseña ───────────────────────────────────────────────────────────────

class TestPasswordRules:
    def test_accepts_good_password(self):
        assert acc.validate_password(GOOD_PW) == GOOD_PW

    def test_too_short(self):
        with pytest.raises(WeakPassword):
            acc.validate_password("corta123")

    def test_exactly_minimum_length_ok(self):
        assert acc.validate_password("abcdefg123") == "abcdefg123"

    def test_too_long(self):
        with pytest.raises(WeakPassword):
            acc.validate_password("a1b2" * 40)

    def test_repetitive(self):
        with pytest.raises(WeakPassword):
            acc.validate_password("aaaaaaaaaaaa")

    @pytest.mark.parametrize("common", ["password123", "1234567890", "OmniaMentis123"])
    def test_common_passwords_rejected(self, common):
        with pytest.raises(WeakPassword):
            acc.validate_password(common)

    def test_cannot_contain_email_local_part(self):
        with pytest.raises(WeakPassword):
            acc.validate_password("xx-estefania-99", "estefania@example.com")

    def test_cannot_be_the_whole_email_even_with_short_local_part(self):
        with pytest.raises(WeakPassword):
            acc.validate_password("ana@example.com", "ana@example.com")
        with pytest.raises(WeakPassword):
            acc.validate_password("ANA@Example.com", "ana@example.com")

    def test_short_email_local_part_is_not_a_problem(self):
        assert acc.validate_password(GOOD_PW, "ab@example.com") == GOOD_PW

    @pytest.mark.parametrize("bad", [None, 12345678901, b"bytes-password"])
    def test_non_string_rejected(self, bad):
        with pytest.raises(WeakPassword):
            acc.validate_password(bad)

    def test_unicode_is_normalized(self):
        composed = "contraseña-larga-ñ"          # ñ compuesta
        decomposed = "contraseña-larga-ñ"   # n + tilde combinante
        assert acc.validate_password(composed) == acc.validate_password(decomposed)


class TestHashFormat:
    def test_versioned_format(self):
        h = acc.hash_password("clave-de-prueba-1", 1000)
        scheme, iters, salt, key = h.split("$")
        assert scheme == "pbkdf2_sha256"
        assert iters == "1000"
        assert salt and key

    def test_roundtrip(self):
        h = acc.hash_password("clave-de-prueba-1", 1000)
        assert acc.verify_hash("clave-de-prueba-1", h) == (True, 1000)
        assert acc.verify_hash("otra-clave-distinta", h) == (False, 1000)

    def test_salt_is_random(self):
        assert acc.hash_password("misma-clave-12", 1000) != acc.hash_password("misma-clave-12", 1000)

    @pytest.mark.parametrize("broken", [
        "", "texto", "a$b$c", "md5$1000$AAAA$BBBB", "pbkdf2_sha256$abc$AAAA$BBBB",
        "pbkdf2_sha256$10$AAAA$BBBB", "pbkdf2_sha256$999999999$AAAA$BBBB",
        "pbkdf2_sha256$1000$!!!$BBBB", "pbkdf2_sha256$1000$$",
    ])
    def test_broken_hash_fails_closed(self, broken):
        assert acc.verify_hash("lo-que-sea-123", broken)[0] is False


# ── Fecha de nacimiento y bandas ─────────────────────────────────────────────

class TestAgeAndBands:
    def test_age_uses_full_date(self):
        assert acc.compute_age(date(2013, 10, 10), TODAY) == 13   # cumple hoy
        assert acc.compute_age(date(2013, 10, 11), TODAY) == 12   # mañana
        assert acc.compute_age(date(2013, 1, 1), TODAY) == 13

    def test_leap_day_birthday(self):
        # Nacida el 29-feb: en año no bisiesto cumple el 1-mar.
        assert acc.compute_age(date(2008, 2, 29), date(2026, 2, 28)) == 17
        assert acc.compute_age(date(2008, 2, 29), date(2026, 3, 1)) == 18

    @pytest.mark.parametrize("age,band", [
        (0, "under_13"), (12, "under_13"), (13, "minor"), (14, "minor"),
        (15, "minor_basic"), (17, "minor_basic"), (18, "adult"), (80, "adult"),
    ])
    def test_band_boundaries(self, age, band):
        assert acc.age_band(age) == band

    def test_parse_accepts_date_and_iso_string(self):
        assert acc.parse_birth_date("1990-05-20", TODAY) == date(1990, 5, 20)
        assert acc.parse_birth_date(date(1990, 5, 20), TODAY) == date(1990, 5, 20)

    @pytest.mark.parametrize("bad", [
        "", "20-05-1990", "1990/05/20", "1990-13-01", "1990-02-30", "mañana",
        None, 19900520, "2999-01-01", "1800-01-01", "1990-5-2",
    ])
    def test_parse_rejects_invalid(self, bad):
        with pytest.raises(InvalidBirthDate):
            acc.parse_birth_date(bad, TODAY)

    def test_future_date_rejected(self):
        with pytest.raises(InvalidBirthDate):
            acc.parse_birth_date("2026-10-11", TODAY)


# ── Nombre para mostrar ──────────────────────────────────────────────────────

class TestDisplayName:
    @pytest.mark.parametrize("raw,expected", [
        ("Ana", "Ana"), ("  Ana   María ", "Ana María"), ("O'Neil", "O'Neil"),
        ("Jean-Luc", "Jean-Luc"), ("José Ñandú", "José Ñandú"), ("Dr. Pérez", "Dr. Pérez"),
        ("李小龍", "李小龍"), ("", None), ("   ", None), (None, None),
    ])
    def test_valid_and_empty(self, raw, expected):
        assert acc.sanitize_display_name(raw) == expected

    @pytest.mark.parametrize("bad", [
        "Ana <b>", "Ana\nIgnora todo", "Ana; DROP", "Ana123", "[SISTEMA]", "a@b",
        "..", "-", "'", "x" * 41, 42, ["Ana"],
    ])
    def test_rejects_symbols_digits_and_overlong(self, bad):
        with pytest.raises(InvalidDisplayName):
            acc.sanitize_display_name(bad)

    def test_max_length_ok(self):
        assert acc.sanitize_display_name("a" * 40) == "a" * 40


# ── Registro ─────────────────────────────────────────────────────────────────

class TestRegister:
    def test_creates_account_and_returns_profile_and_code(self, store):
        uid = new_id()
        profile, code = store.register(uid, "Ana@Example.com", GOOD_PW, ADULT_BIRTH, "Ana")
        assert profile["user_id"] == uid
        assert profile["email"] == "ana@example.com"
        assert profile["display_name"] == "Ana"
        assert profile["age_band"] == "adult"
        assert "birth_date" not in profile
        assert "password_hash" not in profile
        assert len(code.replace("-", "")) == 20

    def test_profile_never_exposes_secrets(self, store):
        profile, _ = register(store)
        assert set(profile) == {"user_id", "email", "display_name", "age_band", "created_at"}

    def test_password_is_not_stored_in_plain_text(self, store, tmp_path):
        register(store, password="mi-clave-secreta-99")
        raw = (tmp_path / "accounts.db").read_bytes()
        assert b"mi-clave-secreta-99" not in raw
        row = store._row("email = ?", ("ana@example.com",))
        assert row["password_hash"].startswith("pbkdf2_sha256$1000$")

    def test_recovery_code_is_stored_only_as_hash(self, store):
        _, code = register(store)
        row = store._row("email = ?", ("ana@example.com",))
        assert code not in row["recovery_hash"]
        assert code.replace("-", "") not in row["recovery_hash"]
        assert len(row["recovery_hash"]) == 64

    def test_duplicate_email_case_insensitive(self, store):
        register(store, email="ana@example.com")
        with pytest.raises(EmailTaken):
            register(store, email="ANA@example.com")

    def test_same_user_id_cannot_register_twice(self, store):
        uid = new_id()
        register(store, email="a@example.com", user_id=uid)
        with pytest.raises(IdentityInUse):
            register(store, email="b@example.com", user_id=uid)

    @pytest.mark.parametrize("bad_id", ["", "no-es-uuid", "123", None, 5,
                                        "ZZZZZZZZ-ZZZZ-ZZZZ-ZZZZ-ZZZZZZZZZZZZ"])
    def test_invalid_user_id(self, store, bad_id):
        with pytest.raises(IdentityInUse):
            store.register(bad_id, "ana@example.com", GOOD_PW, ADULT_BIRTH)

    def test_underage_rejected(self, store):
        with pytest.raises(UnderageError):
            register(store, birth="2013-10-11")   # 12 años y 364 días
        assert store.count() == 0

    def test_exactly_13_accepted_as_minor(self, store):
        profile, _ = register(store, birth="2013-10-10")
        assert profile["age_band"] == "minor"

    @pytest.mark.parametrize("birth,band", [
        ("2012-01-01", "minor"),        # 14
        ("2011-10-10", "minor_basic"),  # 15 hoy
        ("2008-10-11", "minor_basic"),  # 17 y 364 días
        ("2008-10-10", "adult"),        # 18 hoy
    ])
    def test_band_at_registration(self, store, birth, band):
        profile, _ = register(store, birth=birth)
        assert profile["age_band"] == band

    def test_invalid_inputs_do_not_create_rows(self, store):
        for kwargs in (
            dict(email="malo"), dict(password="corta"), dict(birth="no-fecha"),
            dict(name="Ana <b>"),
        ):
            with pytest.raises(Exception):
                register(store, **kwargs)
        assert store.count() == 0

    def test_failed_registration_leaves_store_usable(self, store):
        with pytest.raises(WeakPassword):
            register(store, password="corta")
        profile, _ = register(store)
        assert profile["email"] == "ana@example.com"

    def test_age_band_changes_with_time_but_birth_date_is_fixed(self, tmp_path, clock):
        current = {"d": date(2026, 10, 10)}
        s = AccountStore(tmp_path / "t.db", pbkdf2_iterations=1000, clock=clock,
                         today=lambda: current["d"])
        uid = new_id()
        s.register(uid, "x@example.com", GOOD_PW, "2011-10-11")   # 14 hoy
        assert s.get_profile(uid)["age_band"] == "minor"
        current["d"] = date(2026, 10, 11)                           # cumple 15
        assert s.get_profile(uid)["age_band"] == "minor_basic"
        s.close()


# ── Login ────────────────────────────────────────────────────────────────────

class TestAuthenticate:
    def test_success_returns_profile_and_session_version(self, store):
        profile, _ = register(store, name="Ana")
        got, sv = store.authenticate("ANA@example.com ", GOOD_PW)
        assert got["user_id"] == profile["user_id"]
        assert sv == 1

    def test_wrong_password(self, store):
        register(store)
        with pytest.raises(InvalidCredentials):
            store.authenticate("ana@example.com", "otra-clave-larga-1")

    def test_unknown_email_same_exception(self, store):
        with pytest.raises(InvalidCredentials):
            store.authenticate("nadie@example.com", GOOD_PW)

    @pytest.mark.parametrize("email,pw", [
        (None, GOOD_PW), ("ana@example.com", None), ("", ""), ("no-email", "x"),
        ("ana@example.com", "x" * 5000),
    ])
    def test_garbage_input_is_invalid_credentials(self, store, email, pw):
        register(store)
        with pytest.raises(InvalidCredentials):
            store.authenticate(email, pw)

    def test_error_messages_are_identical(self, store):
        register(store)
        msgs = set()
        for email, pw in (("ana@example.com", "mala-clave-larga-1"),
                          ("nadie@example.com", GOOD_PW)):
            try:
                store.authenticate(email, pw)
            except InvalidCredentials as e:
                msgs.add(str(e))
        assert len(msgs) == 1

    def test_lockout_after_five_failures(self, store, clock):
        register(store)
        for _ in range(5):
            with pytest.raises(InvalidCredentials):
                store.authenticate("ana@example.com", "mala-clave-larga-1")
        # Bloqueada: ni la contraseña correcta entra.
        with pytest.raises(InvalidCredentials):
            store.authenticate("ana@example.com", GOOD_PW)

    def test_lockout_expires(self, store, clock):
        register(store)
        for _ in range(5):
            with pytest.raises(InvalidCredentials):
                store.authenticate("ana@example.com", "mala-clave-larga-1")
        clock.advance(acc.LOCKOUT_SECONDS - 1)
        with pytest.raises(InvalidCredentials):
            store.authenticate("ana@example.com", GOOD_PW)
        clock.advance(2)
        profile, _ = store.authenticate("ana@example.com", GOOD_PW)
        assert profile["email"] == "ana@example.com"

    def test_four_failures_do_not_lock(self, store):
        register(store)
        for _ in range(4):
            with pytest.raises(InvalidCredentials):
                store.authenticate("ana@example.com", "mala-clave-larga-1")
        assert store.authenticate("ana@example.com", GOOD_PW)[0]["email"] == "ana@example.com"

    def test_success_resets_failure_counter(self, store):
        register(store)
        for _ in range(4):
            with pytest.raises(InvalidCredentials):
                store.authenticate("ana@example.com", "mala-clave-larga-1")
        store.authenticate("ana@example.com", GOOD_PW)
        for _ in range(4):
            with pytest.raises(InvalidCredentials):
                store.authenticate("ana@example.com", "mala-clave-larga-1")
        assert store.authenticate("ana@example.com", GOOD_PW)   # sigue sin bloquear

    def test_lockout_is_per_account(self, store):
        register(store, email="a@example.com")
        register(store, email="b@example.com")
        for _ in range(5):
            with pytest.raises(InvalidCredentials):
                store.authenticate("a@example.com", "mala-clave-larga-1")
        assert store.authenticate("b@example.com", GOOD_PW)

    def test_last_login_recorded(self, store, clock):
        profile, _ = register(store)
        clock.advance(100)
        store.authenticate("ana@example.com", GOOD_PW)
        row = store._row("id = ?", (profile["user_id"],))
        assert row["last_login_at"] == clock.t

    def test_old_hash_is_upgraded_on_login(self, tmp_path, clock):
        path = tmp_path / "up.db"
        old = AccountStore(path, pbkdf2_iterations=1000, clock=clock, today=lambda: TODAY)
        old.register(new_id(), "ana@example.com", GOOD_PW, ADULT_BIRTH)
        old.close()
        new = AccountStore(path, pbkdf2_iterations=2000, clock=clock, today=lambda: TODAY)
        new.authenticate("ana@example.com", GOOD_PW)
        assert new._row("email = ?", ("ana@example.com",))["password_hash"].startswith(
            "pbkdf2_sha256$2000$")
        assert new.authenticate("ana@example.com", GOOD_PW)   # sigue funcionando
        new.close()


# ── Lectura y perfil ─────────────────────────────────────────────────────────

class TestProfile:
    def test_get_profile_and_exists(self, store):
        profile, _ = register(store, name="Ana")
        assert store.exists(profile["user_id"])
        assert store.get_profile(profile["user_id"])["display_name"] == "Ana"
        assert not store.exists(new_id())
        assert store.get_profile(new_id()) is None

    def test_update_display_name(self, store):
        profile, _ = register(store)
        updated = store.update_profile(profile["user_id"], "  María   José ")
        assert updated["display_name"] == "María José"

    def test_clear_display_name(self, store):
        profile, _ = register(store, name="Ana")
        assert store.update_profile(profile["user_id"], "")["display_name"] is None

    def test_update_rejects_bad_name_and_keeps_old(self, store):
        profile, _ = register(store, name="Ana")
        with pytest.raises(InvalidDisplayName):
            store.update_profile(profile["user_id"], "Ana <script>")
        assert store.get_profile(profile["user_id"])["display_name"] == "Ana"

    def test_update_unknown_account(self, store):
        with pytest.raises(AccountNotFound):
            store.update_profile(new_id(), "Ana")

    def test_birth_date_cannot_be_changed_through_the_api(self, store):
        import inspect
        assert "birth" not in inspect.signature(store.update_profile).parameters

    def test_session_version_lookup(self, store):
        profile, _ = register(store)
        assert store.get_session_version(profile["user_id"]) == 1
        assert store.get_session_version(new_id()) is None


# ── Cambio de contraseña ─────────────────────────────────────────────────────

class TestChangePassword:
    NEW_PW = "otra-clave-bien-larga-7"

    def test_changes_password_and_bumps_session_version(self, store):
        profile, _ = register(store)
        sv = store.change_password(profile["user_id"], GOOD_PW, self.NEW_PW)
        assert sv == 2
        assert store.get_session_version(profile["user_id"]) == 2
        with pytest.raises(InvalidCredentials):
            store.authenticate("ana@example.com", GOOD_PW)
        assert store.authenticate("ana@example.com", self.NEW_PW)[1] == 2

    def test_wrong_current_password(self, store):
        profile, _ = register(store)
        with pytest.raises(InvalidCredentials):
            store.change_password(profile["user_id"], "no-es-esta-clave-1", self.NEW_PW)
        assert store.get_session_version(profile["user_id"]) == 1

    def test_weak_new_password_rejected_and_old_still_works(self, store):
        profile, _ = register(store)
        with pytest.raises(WeakPassword):
            store.change_password(profile["user_id"], GOOD_PW, "corta")
        assert store.authenticate("ana@example.com", GOOD_PW)

    def test_new_must_differ_from_current(self, store):
        profile, _ = register(store)
        with pytest.raises(WeakPassword):
            store.change_password(profile["user_id"], GOOD_PW, GOOD_PW)

    def test_wrong_current_password_counts_toward_lockout(self, store):
        profile, _ = register(store)
        for _ in range(5):
            with pytest.raises(InvalidCredentials):
                store.change_password(profile["user_id"], "no-es-esta-clave-1", self.NEW_PW)
        with pytest.raises(InvalidCredentials):
            store.authenticate("ana@example.com", GOOD_PW)

    def test_unknown_account(self, store):
        with pytest.raises(InvalidCredentials):
            store.change_password(new_id(), GOOD_PW, self.NEW_PW)


# ── Recuperación ─────────────────────────────────────────────────────────────

class TestRecovery:
    NEW_PW = "clave-recuperada-456"

    def test_recover_sets_new_password_and_rotates_code(self, store):
        profile, code = register(store)
        got, new_code, sv = store.recover("ana@example.com", code, self.NEW_PW)
        assert got["user_id"] == profile["user_id"]
        assert new_code != code
        assert sv == 2
        assert store.authenticate("ana@example.com", self.NEW_PW)
        with pytest.raises(InvalidCredentials):
            store.authenticate("ana@example.com", GOOD_PW)

    def test_used_code_no_longer_works(self, store):
        _, code = register(store)
        store.recover("ana@example.com", code, self.NEW_PW)
        with pytest.raises(InvalidCredentials):
            store.recover("ana@example.com", code, "otra-clave-nueva-88")

    def test_new_code_works(self, store):
        _, code = register(store)
        _, new_code, _ = store.recover("ana@example.com", code, self.NEW_PW)
        store.recover("ana@example.com", new_code, "tercera-clave-larga-5")

    def test_code_is_forgiving_about_format(self, store):
        _, code = register(store)
        sloppy = code.lower().replace("-", " ")
        store.recover("ana@example.com", sloppy, self.NEW_PW)

    def test_wrong_code(self, store):
        register(store)
        with pytest.raises(InvalidCredentials):
            store.recover("ana@example.com", "AAAA-BBBB-CCCC-DDDD-EEEE", self.NEW_PW)

    def test_unknown_email_same_exception(self, store):
        with pytest.raises(InvalidCredentials):
            store.recover("nadie@example.com", "AAAA-BBBB-CCCC-DDDD-EEEE", self.NEW_PW)

    @pytest.mark.parametrize("bad", [None, "", 123, "----"])
    def test_garbage_code(self, store, bad):
        register(store)
        with pytest.raises(InvalidCredentials):
            store.recover("ana@example.com", bad, self.NEW_PW)

    def test_weak_new_password_does_not_burn_the_code(self, store):
        _, code = register(store)
        with pytest.raises(WeakPassword):
            store.recover("ana@example.com", code, "corta")
        store.recover("ana@example.com", code, self.NEW_PW)   # el código sigue sirviendo

    def test_recovery_lockout_after_five_wrong_codes(self, store, clock):
        _, code = register(store)
        for _ in range(5):
            with pytest.raises(InvalidCredentials):
                store.recover("ana@example.com", "AAAA-BBBB-CCCC-DDDD-EEEE", self.NEW_PW)
        with pytest.raises(InvalidCredentials):
            store.recover("ana@example.com", code, self.NEW_PW)   # bloqueada
        clock.advance(acc.LOCKOUT_SECONDS + 1)
        store.recover("ana@example.com", code, self.NEW_PW)

    def test_login_lockout_does_not_block_recovery(self, store):
        _, code = register(store)
        for _ in range(5):
            with pytest.raises(InvalidCredentials):
                store.authenticate("ana@example.com", "mala-clave-larga-1")
        store.recover("ana@example.com", code, self.NEW_PW)
        assert store.authenticate("ana@example.com", self.NEW_PW)   # recuperar desbloquea

    def test_recovery_code_is_bound_to_the_account(self, store):
        _, code_a = register(store, email="a@example.com")
        register(store, email="b@example.com")
        with pytest.raises(InvalidCredentials):
            store.recover("b@example.com", code_a, self.NEW_PW)


class TestRecoveryCodeFormat:
    def test_shape_and_alphabet(self):
        code = acc.generate_recovery_code()
        groups = code.split("-")
        assert len(groups) == 5 and all(len(g) == 4 for g in groups)
        assert set("".join(groups)) <= set(acc.RECOVERY_ALPHABET)

    def test_no_ambiguous_characters(self):
        assert not set("IO01") & set(acc.RECOVERY_ALPHABET)

    def test_codes_are_unique(self):
        assert len({acc.generate_recovery_code() for _ in range(200)}) == 200


# ── Borrado ──────────────────────────────────────────────────────────────────

class TestDelete:
    def test_delete_removes_account_and_identities(self, store):
        profile, _ = register(store)
        store.link_external(profile["user_id"], "supabase", "sub-1")
        assert store.delete_account(profile["user_id"], GOOD_PW) is True
        assert not store.exists(profile["user_id"])
        assert store.find_by_external("supabase", "sub-1") is None

    def test_wrong_password_does_not_delete(self, store):
        profile, _ = register(store)
        with pytest.raises(InvalidCredentials):
            store.delete_account(profile["user_id"], "no-es-esta-clave-1")
        assert store.exists(profile["user_id"])

    def test_email_can_be_reused_after_delete(self, store):
        profile, _ = register(store)
        store.delete_account(profile["user_id"], GOOD_PW)
        register(store)

    def test_unknown_account(self, store):
        with pytest.raises(InvalidCredentials):
            store.delete_account(new_id(), GOOD_PW)


# ── Identidades externas ─────────────────────────────────────────────────────

class TestExternalIdentities:
    def test_link_and_find(self, store):
        profile, _ = register(store)
        store.link_external(profile["user_id"], "Supabase", "abc-123")
        assert store.find_by_external("supabase", "abc-123") == profile["user_id"]

    def test_same_identity_cannot_link_twice(self, store):
        a, _ = register(store, email="a@example.com")
        b, _ = register(store, email="b@example.com")
        store.link_external(a["user_id"], "firebase", "uid-9")
        with pytest.raises(IdentityInUse):
            store.link_external(b["user_id"], "firebase", "uid-9")

    def test_link_unknown_account(self, store):
        with pytest.raises(AccountNotFound):
            store.link_external(new_id(), "firebase", "uid-9")

    def test_find_missing_returns_none(self, store):
        assert store.find_by_external("firebase", "nada") is None

    @pytest.mark.parametrize("provider,subject", [("", "x"), ("x", ""), (None, "x"), ("x", 5)])
    def test_invalid_identity(self, store, provider, subject):
        profile, _ = register(store)
        with pytest.raises(IdentityInUse):
            store.link_external(profile["user_id"], provider, subject)


# ── Persistencia y concurrencia ──────────────────────────────────────────────

class TestPersistenceAndThreads:
    def test_data_survives_reopen(self, tmp_path, clock):
        path = tmp_path / "persist.db"
        s1 = AccountStore(path, pbkdf2_iterations=1000, clock=clock, today=lambda: TODAY)
        profile, code = s1.register(new_id(), "ana@example.com", GOOD_PW, ADULT_BIRTH, "Ana")
        s1.close()
        s2 = AccountStore(path, pbkdf2_iterations=1000, clock=clock, today=lambda: TODAY)
        assert s2.get_profile(profile["user_id"])["display_name"] == "Ana"
        assert s2.authenticate("ana@example.com", GOOD_PW)
        s2.recover("ana@example.com", code, "clave-recuperada-456")
        s2.close()

    def test_creates_missing_parent_directory(self, tmp_path):
        s = AccountStore(tmp_path / "a" / "b" / "accounts.db", pbkdf2_iterations=1000)
        assert (tmp_path / "a" / "b" / "accounts.db").exists()
        s.close()

    def test_close_is_idempotent(self, tmp_path):
        s = AccountStore(tmp_path / "c.db", pbkdf2_iterations=1000)
        s.close()
        s.close()

    def test_concurrent_registrations_same_email_only_one_wins(self, store):
        results = []

        def worker():
            try:
                register(store, email="carrera@example.com")
                results.append("ok")
            except EmailTaken:
                results.append("taken")

        threads = [threading.Thread(target=worker) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert results.count("ok") == 1
        assert results.count("taken") == 7
        assert store.count() == 1

    def test_concurrent_distinct_registrations(self, store):
        def worker(i):
            register(store, email=f"user{i}@example.com")

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert store.count() == 10

    def test_schema_has_no_birth_date_in_profile_queries(self, store):
        profile, _ = register(store)
        assert "birth_date" not in store.get_profile(profile["user_id"])

    def test_foreign_keys_are_enforced(self, store):
        with pytest.raises(sqlite3.IntegrityError):
            store._conn.execute(
                "INSERT INTO external_identities (provider, subject, account_id, created_at)"
                " VALUES ('x', 'y', 'no-existe', 0)"
            )