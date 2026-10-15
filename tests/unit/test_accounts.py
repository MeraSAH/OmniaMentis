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

import re
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
    ConsentRequired,
    EmailTaken,
    GuardianPending,
    GuardianRequired,
    GuardianResendTooSoon,
    GuardianTokenInvalid,
    IdentityInUse,
    InvalidBirthDate,
    InvalidCredentials,
    InvalidDisplayName,
    InvalidEmail,
    TermsOutdated,
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
        assert set(profile) == {"user_id", "email", "display_name", "age_band", "created_at",
                                "guardian_pending"}

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


# ── Consentimiento (2026-10-11) ──────────────────────────────────────────────

def good_consent(**over):
    c = {"version": acc.TERMS_VERSION, "terms": True, "sensitive": True, "guardian": False}
    c.update(over)
    return c


def register_c(store, consent, birth=ADULT_BIRTH, email="ana@example.com", require=True):
    return store.register(new_id(), email, GOOD_PW, birth, None,
                          consent=consent, require_consent=require)


class TestValidateConsent:

    def test_adult_with_both_acceptances(self):
        r = acc.validate_consent("adult", good_consent())
        assert r == {"terms_version": acc.TERMS_VERSION, "guardian_declared": False}

    @pytest.mark.parametrize("bad", [None, "si", 1, True, [], ()])
    def test_non_dict_is_rejected(self, bad):
        with pytest.raises(ConsentRequired):
            acc.validate_consent("adult", bad)

    @pytest.mark.parametrize("field,value", [
        (f, v) for f in ("terms", "sensitive")
        for v in (False, None, "true", 1, "on", 0, "yes")
    ])
    def test_only_json_true_counts(self, field, value):
        with pytest.raises(ConsentRequired):
            acc.validate_consent("adult", good_consent(**{field: value}))

    @pytest.mark.parametrize("field", ["terms", "sensitive"])
    def test_missing_field_is_rejected(self, field):
        c = good_consent()
        del c[field]
        with pytest.raises(ConsentRequired):
            acc.validate_consent("adult", c)

    def test_missing_version_is_consent_required_not_outdated(self):
        with pytest.raises(ConsentRequired):
            acc.validate_consent("adult", {"terms": True, "sensitive": True})
        with pytest.raises(ConsentRequired):
            acc.validate_consent("adult", {})

    @pytest.mark.parametrize("version", [None, "", "2020-01-01", 20261011])
    def test_wrong_version_is_terms_outdated(self, version):
        with pytest.raises(TermsOutdated):
            acc.validate_consent("adult", good_consent(version=version))

    @pytest.mark.parametrize("band", ["minor", "minor_basic", "adult"])
    def test_declarative_guardian_flag_no_longer_counts(self, band):
        """Resolución 2026-10-14: la casilla declarativa se eliminó. El
        consentimiento de 13-14 años lo da el representante por correo
        (confirm_guardian); 15-17 consienten solos."""
        assert acc.validate_consent(band, good_consent())["guardian_declared"] is False
        assert acc.validate_consent(band, good_consent(guardian=True))["guardian_declared"] is False

    def test_error_codes_are_stable(self):
        assert ConsentRequired.code == "consent_required"
        assert TermsOutdated.code == "terms_outdated"

    def test_version_is_a_date_string(self):
        assert re.match(r"^\d{4}-\d{2}-\d{2}$", acc.TERMS_VERSION)


class TestConsentStorage:

    def test_registration_requires_consent_when_asked(self, store):
        with pytest.raises(ConsentRequired):
            register_c(store, None)
        assert store.count() == 0

    def test_failed_consent_creates_no_account(self, store):
        with pytest.raises(ConsentRequired):
            register_c(store, good_consent(sensitive=False))
        assert store.count() == 0

    def test_minor_of_15_to_17_consents_alone(self, store):
        profile, _ = register_c(store, good_consent(), birth="2010-03-01")
        assert profile["age_band"] == "minor_basic"
        assert profile["guardian_pending"] is False
        assert store.get_consent(profile["user_id"])["guardian_declared"] is False

    def test_consent_is_stored_with_version_and_timestamps(self, store, clock):
        profile, _ = register_c(store, good_consent())
        c = store.get_consent(profile["user_id"])
        assert c["terms_version"] == acc.TERMS_VERSION
        assert c["terms_accepted_at"] == c["sensitive_consent_at"]
        assert c["terms_accepted_at"].endswith("+00:00")
        assert c["guardian_declared"] is False

    def test_consent_is_not_part_of_the_public_profile(self, store):
        profile, _ = register_c(store, good_consent())
        assert set(profile) == {"user_id", "email", "display_name", "age_band", "created_at",
                                "guardian_pending"}

    def test_without_requirement_and_without_consent_nothing_is_recorded(self, store):
        profile, _ = register(store)
        assert store.get_consent(profile["user_id"]) is None

    def test_consent_given_without_requirement_is_still_validated(self, store):
        with pytest.raises(ConsentRequired):
            register_c(store, good_consent(terms=False), require=False)

    def test_get_consent_of_unknown_account_is_none(self, store):
        assert store.get_consent(new_id()) is None

    def test_consent_dies_with_the_account(self, store):
        profile, _ = register_c(store, good_consent())
        store.delete_account(profile["user_id"], GOOD_PW)
        assert store.get_consent(profile["user_id"]) is None


class TestMigration:

    def test_old_database_without_consent_columns_is_upgraded(self, tmp_path):
        path = tmp_path / "old.db"
        con = sqlite3.connect(path)
        con.executescript("""
            CREATE TABLE accounts (
                id TEXT PRIMARY KEY, email TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL,
                display_name TEXT, birth_date TEXT NOT NULL,
                session_version INTEGER NOT NULL DEFAULT 1,
                failed_attempts INTEGER NOT NULL DEFAULT 0, locked_until REAL NOT NULL DEFAULT 0,
                recovery_hash TEXT NOT NULL, recovery_failed INTEGER NOT NULL DEFAULT 0,
                recovery_locked_until REAL NOT NULL DEFAULT 0,
                created_at REAL NOT NULL, updated_at REAL NOT NULL, last_login_at REAL);
        """)
        uid = new_id()
        con.execute(
            "INSERT INTO accounts (id, email, password_hash, birth_date, recovery_hash,"
            " created_at, updated_at) VALUES (?, 'viejo@example.com', ?, '1990-05-20', 'x', 1, 1)",
            (uid, acc.hash_password(GOOD_PW, 1000)),
        )
        con.commit()
        con.close()

        s = AccountStore(path, pbkdf2_iterations=1000, today=lambda: TODAY)
        try:
            assert s.get_profile(uid)["email"] == "viejo@example.com"
            assert s.get_consent(uid) is None            # cuenta anterior: sin registro
            profile, _ = s.authenticate("viejo@example.com", GOOD_PW)
            assert profile["user_id"] == uid
            new_profile, _ = s.register(new_id(), "nuevo@example.com", GOOD_PW, ADULT_BIRTH,
                                        None, consent=good_consent(), require_consent=True)
            assert s.get_consent(new_profile["user_id"])["terms_version"] == acc.TERMS_VERSION
        finally:
            s.close()

    def test_reopening_a_current_database_is_harmless(self, tmp_path):
        path = tmp_path / "a.db"
        s1 = AccountStore(path, pbkdf2_iterations=1000, today=lambda: TODAY)
        profile, _ = s1.register(new_id(), "a@example.com", GOOD_PW, ADULT_BIRTH,
                                 None, consent=good_consent(), require_consent=True)
        s1.close()
        s2 = AccountStore(path, pbkdf2_iterations=1000, today=lambda: TODAY)
        try:
            assert s2.get_consent(profile["user_id"]) is not None
        finally:
            s2.close()


class TestExportAccount:

    def test_returns_owner_data_including_birth_date(self, store):
        profile, _ = register_c(store, good_consent())
        data = store.export_account(profile["user_id"], GOOD_PW)
        assert data["email"] == "ana@example.com"
        assert data["birth_date"] == ADULT_BIRTH
        assert data["age_band"] == "adult"
        assert data["consent"]["terms_version"] == acc.TERMS_VERSION
        assert data["created_at"].endswith("+00:00")

    def test_never_includes_secrets(self, store):
        profile, code = register_c(store, good_consent())
        raw = repr(store.export_account(profile["user_id"], GOOD_PW))
        assert "pbkdf2" not in raw
        assert code not in raw
        assert "recovery" not in raw and "password" not in raw

    def test_wrong_password_is_invalid_credentials(self, store):
        profile, _ = register_c(store, good_consent())
        with pytest.raises(InvalidCredentials):
            store.export_account(profile["user_id"], "otra-clave-larga-1")

    def test_wrong_passwords_count_towards_lockout(self, store):
        profile, _ = register_c(store, good_consent())
        for _ in range(acc.MAX_FAILED_ATTEMPTS):
            with pytest.raises(InvalidCredentials):
                store.export_account(profile["user_id"], "otra-clave-larga-1")
        with pytest.raises(InvalidCredentials):
            store.export_account(profile["user_id"], GOOD_PW)

    def test_unknown_account_is_invalid_credentials(self, store):
        with pytest.raises(InvalidCredentials):
            store.export_account(new_id(), GOOD_PW)

    def test_account_without_consent_record_exports_none(self, store):
        profile, _ = register(store)
        assert store.export_account(profile["user_id"], GOOD_PW)["consent"] is None


# ── Representante legal, 13-14 años (resolución 2026-10-14) ──────────────────

MINOR_BIRTH = "2012-03-01"        # 14 años con TODAY = 2026-10-10 -> banda "minor"
TEEN_BIRTH = "2010-03-01"         # 16 años -> consiente solo
GUARDIAN = "mama@example.com"


def register_minor(store, email="nino@example.com", guardian=GUARDIAN, consent=None, **kw):
    return store.register(new_id(), email, GOOD_PW, MINOR_BIRTH, None,
                          consent=consent or good_consent(), require_consent=True,
                          guardian_email=guardian, **kw)


def confirm_consent(**over):
    c = {"version": acc.TERMS_VERSION, "terms": True, "sensitive": True}
    c.update(over)
    return c


class TestGuardianRegistration:

    def test_minor_needs_a_guardian_email(self, store):
        with pytest.raises(GuardianRequired):
            register_minor(store, guardian=None)
        with pytest.raises(GuardianRequired):
            register_minor(store, guardian="")
        assert store.count() == 0

    @pytest.mark.parametrize("bad", ["no-es-email", "a@b", 12, ["x@y.com"], "x@@y.com"])
    def test_invalid_guardian_email_is_rejected(self, store, bad):
        with pytest.raises(GuardianRequired):
            register_minor(store, guardian=bad)
        assert store.count() == 0

    def test_guardian_email_must_differ_from_own(self, store):
        with pytest.raises(GuardianRequired):
            register_minor(store, email="nino@example.com", guardian="NINO@example.com")
        assert store.count() == 0

    def test_minor_account_is_born_pending(self, store):
        profile, _ = register_minor(store)
        assert profile["age_band"] == "minor"
        assert profile["guardian_pending"] is True
        assert store.get_consent(profile["user_id"])["guardian_confirmed_at"] is None

    def test_teen_15_to_17_is_not_pending_and_needs_no_guardian(self, store):
        profile, _ = store.register(new_id(), "t@example.com", GOOD_PW, TEEN_BIRTH, None,
                                    consent=good_consent(), require_consent=True)
        assert profile["age_band"] == "minor_basic"
        assert profile["guardian_pending"] is False

    def test_adult_ignores_and_does_not_store_a_guardian_email(self, store):
        profile, _ = store.register(new_id(), "a@example.com", GOOD_PW, ADULT_BIRTH, None,
                                    consent=good_consent(), require_consent=True,
                                    guardian_email=GUARDIAN)
        assert profile["guardian_pending"] is False
        assert store.export_account(profile["user_id"], GOOD_PW)["guardian"] is None

    def test_guardian_email_is_optional_without_the_consent_requirement(self, store):
        profile, _ = store.register(new_id(), "n@example.com", GOOD_PW, MINOR_BIRTH, None)
        assert profile["guardian_pending"] is True      # sin confirmar: sigue bloqueada

    def test_under_13_is_still_refused(self, store):
        with pytest.raises(acc.UnderageError):
            store.register(new_id(), "k@example.com", GOOD_PW, "2015-01-01", None,
                           consent=good_consent(), require_consent=True, guardian_email=GUARDIAN)


class TestGuardianLoginGate:

    def test_pending_account_cannot_log_in(self, store):
        register_minor(store)
        with pytest.raises(GuardianPending):
            store.authenticate("nino@example.com", GOOD_PW)

    def test_wrong_password_does_not_reveal_pending_state(self, store):
        register_minor(store)
        with pytest.raises(InvalidCredentials):
            store.authenticate("nino@example.com", "otra-clave-larga-1")

    def test_pending_login_attempt_does_not_record_a_login(self, store):
        profile, _ = register_minor(store)
        with pytest.raises(GuardianPending):
            store.authenticate("nino@example.com", GOOD_PW)
        assert store.export_account(profile["user_id"], GOOD_PW)["last_login_at"] is None

    def test_allow_pending_returns_the_profile(self, store):
        profile, _ = register_minor(store)
        got, version = store.authenticate("nino@example.com", GOOD_PW, allow_pending=True)
        assert got["user_id"] == profile["user_id"] and got["guardian_pending"] is True
        assert version == 1

    def test_error_codes_and_statuses_are_stable(self):
        assert GuardianRequired.code == "guardian_email_required"
        assert GuardianPending.code == "guardian_pending"
        assert GuardianTokenInvalid.code == "guardian_token_invalid"
        assert GuardianResendTooSoon.code == "guardian_resend_wait"
        assert acc.GuardianMailUnavailable.code == "guardian_mail_unavailable"


class TestGuardianToken:

    def test_issue_returns_target_and_token(self, store):
        profile, _ = register_minor(store)
        target, token = store.issue_guardian_token(profile["user_id"])
        assert target == GUARDIAN
        assert len(token) >= 32

    def test_token_is_never_stored_in_clear(self, store):
        profile, _ = register_minor(store)
        _, token = store.issue_guardian_token(profile["user_id"])
        dump = repr([tuple(r) for r in store._conn.execute("SELECT * FROM accounts")])
        assert token not in dump

    def test_tokens_are_unique(self, store, clock):
        profile, _ = register_minor(store)
        _, t1 = store.issue_guardian_token(profile["user_id"])
        clock.advance(acc.GUARDIAN_RESEND_COOLDOWN_SECONDS + 1)
        _, t2 = store.issue_guardian_token(profile["user_id"])
        assert t1 != t2

    def test_adult_cannot_get_a_token(self, store):
        profile, _ = register(store)
        with pytest.raises(GuardianTokenInvalid):
            store.issue_guardian_token(profile["user_id"])

    def test_unknown_account(self, store):
        with pytest.raises(AccountNotFound):
            store.issue_guardian_token(new_id())

    def test_resend_cooldown(self, store, clock):
        profile, _ = register_minor(store)
        store.issue_guardian_token(profile["user_id"])
        with pytest.raises(GuardianResendTooSoon):
            store.issue_guardian_token(profile["user_id"])
        clock.advance(acc.GUARDIAN_RESEND_COOLDOWN_SECONDS + 1)
        store.issue_guardian_token(profile["user_id"])

    def test_released_cooldown_allows_immediate_retry(self, store):
        profile, _ = register_minor(store)
        store.issue_guardian_token(profile["user_id"])
        store.release_guardian_cooldown(profile["user_id"])
        store.issue_guardian_token(profile["user_id"])

    def test_new_token_invalidates_the_previous_one(self, store, clock):
        profile, _ = register_minor(store)
        _, old = store.issue_guardian_token(profile["user_id"])
        clock.advance(acc.GUARDIAN_RESEND_COOLDOWN_SECONDS + 1)
        _, new = store.issue_guardian_token(profile["user_id"])
        with pytest.raises(GuardianTokenInvalid):
            store.confirm_guardian(old, confirm_consent())
        assert store.confirm_guardian(new, confirm_consent()) is True

    def test_guardian_email_can_be_corrected_while_pending(self, store, clock):
        profile, _ = register_minor(store, guardian="mamaa@example.com")      # errata
        clock.advance(acc.GUARDIAN_RESEND_COOLDOWN_SECONDS + 1)
        target, _ = store.issue_guardian_token(profile["user_id"], "mama@example.com")
        assert target == "mama@example.com"
        assert store.export_account(profile["user_id"], GOOD_PW)["guardian"]["email"] == "mama@example.com"

    def test_correction_still_validates_the_email(self, store, clock):
        profile, _ = register_minor(store)
        clock.advance(acc.GUARDIAN_RESEND_COOLDOWN_SECONDS + 1)
        with pytest.raises(GuardianRequired):
            store.issue_guardian_token(profile["user_id"], "nino@example.com")
        with pytest.raises(GuardianRequired):
            store.issue_guardian_token(profile["user_id"], "basura")

    def test_legacy_pending_account_without_guardian_email_needs_one(self, store):
        profile, _ = store.register(new_id(), "viejo@example.com", GOOD_PW, MINOR_BIRTH, None)
        with pytest.raises(GuardianRequired):
            store.issue_guardian_token(profile["user_id"])
        target, token = store.issue_guardian_token(profile["user_id"], GUARDIAN)
        assert target == GUARDIAN and token


class TestGuardianConfirm:

    def _pending(self, store):
        profile, _ = register_minor(store)
        _, token = store.issue_guardian_token(profile["user_id"])
        return profile, token

    def test_confirmation_unlocks_login_and_records_proof(self, store, clock):
        profile, token = self._pending(store)
        assert store.confirm_guardian(token, confirm_consent()) is True
        got, _ = store.authenticate("nino@example.com", GOOD_PW)
        assert got["guardian_pending"] is False
        c = store.get_consent(profile["user_id"])
        assert c["guardian_terms_version"] == acc.TERMS_VERSION
        assert c["guardian_confirmed_at"].endswith("+00:00")

    def test_token_is_single_use(self, store):
        _, token = self._pending(store)
        store.confirm_guardian(token, confirm_consent())
        with pytest.raises(GuardianTokenInvalid):
            store.confirm_guardian(token, confirm_consent())

    def test_token_expires_after_seven_days(self, store, clock):
        _, token = self._pending(store)
        clock.advance(acc.GUARDIAN_TOKEN_TTL_SECONDS + 1)
        with pytest.raises(GuardianTokenInvalid):
            store.confirm_guardian(token, confirm_consent())

    def test_token_still_valid_just_before_expiry(self, store, clock):
        _, token = self._pending(store)
        clock.advance(acc.GUARDIAN_TOKEN_TTL_SECONDS - 5)
        assert store.confirm_guardian(token, confirm_consent()) is True

    @pytest.mark.parametrize("bad", [None, "", "corto", 123, ["x"], "a" * 31, "a" * 129,
                                     "con espacios " * 4, "%" * 40])
    def test_malformed_tokens_are_invalid(self, store, bad):
        self._pending(store)
        with pytest.raises(GuardianTokenInvalid):
            store.confirm_guardian(bad, confirm_consent())

    def test_unknown_well_formed_token_is_invalid(self, store):
        self._pending(store)
        with pytest.raises(GuardianTokenInvalid):
            store.confirm_guardian("A" * 43, confirm_consent())

    @pytest.mark.parametrize("field", ["terms", "sensitive"])
    def test_guardian_must_accept_everything(self, store, field):
        _, token = self._pending(store)
        with pytest.raises(ConsentRequired):
            store.confirm_guardian(token, confirm_consent(**{field: False}))
        with pytest.raises(ConsentRequired):
            store.confirm_guardian(token, confirm_consent(**{field: "true"}))

    def test_rejected_consent_does_not_burn_the_token(self, store):
        _, token = self._pending(store)
        with pytest.raises(ConsentRequired):
            store.confirm_guardian(token, confirm_consent(sensitive=False))
        assert store.confirm_guardian(token, confirm_consent()) is True

    def test_outdated_text_version_is_rejected(self, store):
        _, token = self._pending(store)
        with pytest.raises(TermsOutdated):
            store.confirm_guardian(token, confirm_consent(version="2020-01-01"))

    def test_missing_consent_is_rejected(self, store):
        _, token = self._pending(store)
        with pytest.raises(ConsentRequired):
            store.confirm_guardian(token, None)

    def test_turning_15_unblocks_without_confirmation(self, tmp_path, clock):
        today = {"d": TODAY}
        s = AccountStore(tmp_path / "t.db", pbkdf2_iterations=1000, clock=clock,
                         today=lambda: today["d"])
        try:
            s.register(new_id(), "nino@example.com", GOOD_PW, "2011-12-01", None,
                       consent=good_consent(), require_consent=True, guardian_email=GUARDIAN)
            with pytest.raises(GuardianPending):
                s.authenticate("nino@example.com", GOOD_PW)
            today["d"] = date(2026, 12, 2)                  # cumple 15
            got, _ = s.authenticate("nino@example.com", GOOD_PW)
            assert got["age_band"] == "minor_basic" and got["guardian_pending"] is False
        finally:
            s.close()


class TestGuardianCleanup:

    def test_abort_pending_deletes_only_pending_minors(self, store):
        pending, _ = register_minor(store)
        adult, _ = register(store, email="adulto@example.com")
        assert store.abort_pending(adult["user_id"]) is False
        assert store.exists(adult["user_id"])
        assert store.abort_pending(pending["user_id"]) is True
        assert not store.exists(pending["user_id"])
        assert store.abort_pending(pending["user_id"]) is False

    def test_abort_does_not_touch_confirmed_accounts(self, store):
        profile, _ = register_minor(store)
        _, token = store.issue_guardian_token(profile["user_id"])
        store.confirm_guardian(token, confirm_consent())
        assert store.abort_pending(profile["user_id"]) is False
        assert store.exists(profile["user_id"])

    def test_prune_unconfirmed_after_30_days(self, store, clock):
        pending, _ = register_minor(store)
        confirmed, _ = register_minor(store, email="otro@example.com", guardian="papa@example.com")
        _, token = store.issue_guardian_token(confirmed["user_id"])
        store.confirm_guardian(token, confirm_consent())
        adult, _ = register(store, email="adulto@example.com")
        clock.advance(31 * 86400)
        removed = store.prune_unconfirmed()
        assert removed == [pending["user_id"]]
        assert not store.exists(pending["user_id"])
        assert store.exists(confirmed["user_id"]) and store.exists(adult["user_id"])

    def test_prune_keeps_recent_pending(self, store, clock):
        pending, _ = register_minor(store)
        clock.advance(29 * 86400)
        assert store.prune_unconfirmed() == []
        assert store.exists(pending["user_id"])

    def test_prune_with_zero_days_is_disabled(self, store, clock):
        register_minor(store)
        clock.advance(400 * 86400)
        assert store.prune_unconfirmed(0) == []


class TestGuardianExportAndMigration:

    def test_export_includes_guardian_proof(self, store):
        profile, _ = register_minor(store)
        _, token = store.issue_guardian_token(profile["user_id"])
        store.confirm_guardian(token, confirm_consent())
        data = store.export_account(profile["user_id"], GOOD_PW)
        assert data["guardian"]["email"] == GUARDIAN
        assert data["guardian"]["confirmed_at"].endswith("+00:00")
        assert "token" not in repr(data).lower()

    def test_old_database_gets_guardian_columns(self, tmp_path):
        path = tmp_path / "old2.db"
        con = sqlite3.connect(path)
        con.executescript("""
            CREATE TABLE accounts (
                id TEXT PRIMARY KEY, email TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL,
                display_name TEXT, birth_date TEXT NOT NULL,
                session_version INTEGER NOT NULL DEFAULT 1,
                failed_attempts INTEGER NOT NULL DEFAULT 0, locked_until REAL NOT NULL DEFAULT 0,
                recovery_hash TEXT NOT NULL, recovery_failed INTEGER NOT NULL DEFAULT 0,
                recovery_locked_until REAL NOT NULL DEFAULT 0,
                created_at REAL NOT NULL, updated_at REAL NOT NULL, last_login_at REAL,
                terms_version TEXT, terms_accepted_at REAL, sensitive_consent_at REAL,
                guardian_declared INTEGER NOT NULL DEFAULT 0);
        """)
        uid = new_id()
        con.execute(
            "INSERT INTO accounts (id, email, password_hash, birth_date, recovery_hash,"
            " created_at, updated_at, guardian_declared) VALUES (?, 'm@example.com', ?, ?, 'x', 1, 1, 1)",
            (uid, acc.hash_password(GOOD_PW, 1000), MINOR_BIRTH),
        )
        con.commit()
        con.close()
        s = AccountStore(path, pbkdf2_iterations=1000, today=lambda: TODAY)
        try:
            # La antigua casilla declarativa ya no vale: pasa a pendiente.
            assert s.get_profile(uid)["guardian_pending"] is True
            with pytest.raises(GuardianPending):
                s.authenticate("m@example.com", GOOD_PW)
        finally:
            s.close()