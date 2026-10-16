"""
* UBICACIÓN: OmniaMentis/src/core/auth/accounts.py
* PROPÓSITO: Cuentas de usuario de OmniaMentis (registro, login, perfil,
*            cambio y recuperación de contraseña, borrado de cuenta) en
*            una base SQLite propia. Es INDEPENDIENTE del panel del Fons
*            (fons_auth.py): otra clave, otro token, otra tabla. Ninguna
*            cuenta de usuario concede acceso al Fons.
* DEPENDENCIAS: stdlib únicamente (hashlib, hmac, sqlite3, secrets...)
* CREADO: 2026-10-10
* ÚLTIMA MODIFICACIÓN: 2026-10-15
* ESTADO: Producción
*
* DECISIONES DE DISEÑO
*
* 1. Contraseñas: PBKDF2-HMAC-SHA256 (stdlib, sin compilar nada en
*    Windows). 600 000 iteraciones por defecto (recomendación OWASP para
*    PBKDF2-SHA256). El hash se guarda con formato versionado
*    "pbkdf2_sha256$iteraciones$sal$hash": si en el futuro se suben las
*    iteraciones, los hashes viejos siguen verificando y se actualizan
*    solos en el siguiente login correcto.
*
* 2. Sin enumeración de cuentas en el login: email inexistente, contraseña
*    incorrecta y cuenta bloqueada producen la MISMA excepción
*    (InvalidCredentials) y el mismo trabajo de CPU (se verifica un hash
*    señuelo cuando no hay cuenta o está bloqueada). El registro sí
*    informa si un email ya existe (inevitable en cualquier registro);
*    la API lo protege con límite de intentos por IP.
*
* 3. Bloqueo por fuerza bruta: 5 fallos seguidos bloquean el login de esa
*    cuenta 15 minutos. La recuperación con código tiene su propio
*    contador, para que un atacante que bloquee el login no impida al
*    dueño recuperar su cuenta.
*
* 4. Recuperación sin correo (aún no hay servicio de email): al registrarse
*    y al recuperar se entrega UNA vez un código de 20 caracteres (100
*    bits). Solo se guarda su hash. Usarlo lo reemplaza por uno nuevo.
*
* 5. Fecha de nacimiento: obligatoria al registrarse, NO editable después
*    (evita que un menor se haga pasar por adulto). Solo sale del
*    servidor la BANDA de edad: "minor" (13-14), "minor_basic" (15-17),
*    "adult" (18+). Menores de 13 años no pueden crear cuenta (mismo
*    mínimo que Corporal; su camino será otra decisión). La banda
*    "adult" NO equivale a "adult_student": eso exige verificación.
*
* 6. session_version: cada cuenta tiene un contador que sube al cambiar o
*    recuperar la contraseña. La cookie de sesión lleva el valor con el
*    que se inició; si no coincide, la sesión deja de valer. Así cambiar
*    la contraseña cierra las sesiones abiertas en otros dispositivos.
*
* 7. external_identities: tabla lista para enlazar cuentas de otros
*    sistemas del ecosistema (Supabase/Corporal, Firebase/NutriVida) sin
*    cambiar el esquema. Hoy no se usa.
*
* 8. El id de la cuenta ES el user_id (uuid) de la sesión anónima que se
*    registró: la consciencia, memoria y diario de esa persona pasan a su
*    cuenta sin migrar nada.
*
* 9. Consentimiento (2026-10-11): al registrarse se exigen DOS aceptaciones
*    explícitas y separadas (Términos + Privacidad, y tratamiento de
*    contenido emocional/sensible), ligadas a la versión de los textos
*    (TERMS_VERSION); si el cliente envía otra versión se rechaza para que
*    la persona lea la vigente. Menores de 18 deben además declarar que su
*    representante legal está informado y autoriza (declaración, no
*    verificación: la verificación real queda para cuando haya correo).
*    Se guarda versión y fecha de cada consentimiento (prueba y derecho de
*    acceso). export_account() entrega los datos de la cuenta a su titular.
*
* 10. Edad y representante (2026-10-14, resolución del especialista; base:
*    LOPDP y su reglamento, a confirmar con el abogado): menores de 13 años,
*    prohibido. 13-14 años ("minor"): el consentimiento lo da el
*    REPRESENTANTE LEGAL de forma verificable: la cuenta nace "pendiente" y
*    no puede iniciar sesión hasta que el representante abra el enlace
*    único (token de 256 bits, solo se guarda su hash, vence a los 7 días,
*    un solo uso) que se envió a SU correo y acepte Términos, Privacidad y
*    el tratamiento de datos sensibles. Se eliminó la casilla declarativa.
*    No se piden copias de cédula (minimización de datos). 15-17 años
*    ("minor_basic") y adultos: consentimiento directo. Las cuentas que
*    siguen pendientes tras GUARDIAN_PENDING_PRUNE_DAYS se borran solas.
"""

import base64
import hashlib
import hmac
import os
import re
import secrets
import sqlite3
import threading
import time
import unicodedata
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Tuple

# ── Parámetros ───────────────────────────────────────────────────────────────

PBKDF2_ITERATIONS = 600_000
HASH_SCHEME = "pbkdf2_sha256"
SALT_BYTES = 16
MIN_ITERATIONS_ACCEPTED = 1_000          # tope inferior al leer hashes
MAX_ITERATIONS_ACCEPTED = 10_000_000     # tope superior al leer hashes

MIN_PASSWORD_LENGTH = 10
MAX_PASSWORD_LENGTH = 128

MAX_FAILED_ATTEMPTS = 5
LOCKOUT_SECONDS = 15 * 60

MIN_AGE = 13
MAX_AGE = 120

DISPLAY_NAME_MAX = 40

# Versión de los textos legales (privacidad, términos, cookies). Súbela cada
# vez que cambien de fondo; coincide con la fecha de "Última actualización".
TERMS_VERSION = "2026-10-15"

# Confirmación del representante legal (13-14 años).
GUARDIAN_TOKEN_TTL_SECONDS = 7 * 86400          # el enlace vence a los 7 días
GUARDIAN_RESEND_COOLDOWN_SECONDS = 10 * 60      # evita inundar el correo del representante
GUARDIAN_PENDING_PRUNE_DAYS = 30                # cuenta sin confirmar: se borra
_GUARDIAN_TOKEN_RE = re.compile(r"^[A-Za-z0-9_\-]{32,128}$")

MAX_EMAIL_LENGTH = 254
MAX_EMAIL_LOCAL_LENGTH = 64

RECOVERY_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # sin I, O, 0, 1
RECOVERY_LENGTH = 20

_EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(?:\.[A-Za-z0-9\-]+)+$")
_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)

_COMMON_PASSWORDS = frozenset({
    "password", "password1", "password12", "password123", "contrasena",
    "contrasena1", "contrasena123", "1234567890", "12345678910",
    "0123456789", "qwertyuiop", "asdfghjkl1", "abcdefghij", "iloveyou12",
    "omniamentis", "omniamentis1", "omniamentis123", "admin12345",
    "letmein123", "welcome123",
})

_DUMMY_PASSWORD = "contraseña-señuelo-para-igualar-tiempos"


# ── Excepciones ──────────────────────────────────────────────────────────────

class AccountError(Exception):
    """Base de los errores de cuentas. `code` es estable (para la API)."""
    code = "account_error"


class InvalidEmail(AccountError):
    code = "invalid_email"


class WeakPassword(AccountError):
    code = "weak_password"


class EmailTaken(AccountError):
    code = "email_taken"


class IdentityInUse(AccountError):
    """El user_id ya pertenece a otra cuenta (o la identidad externa)."""
    code = "identity_in_use"


class InvalidBirthDate(AccountError):
    code = "invalid_birth_date"


class UnderageError(AccountError):
    code = "underage"


class InvalidDisplayName(AccountError):
    code = "invalid_display_name"


class InvalidCredentials(AccountError):
    """Credenciales incorrectas, cuenta inexistente o bloqueada (indistinguibles)."""
    code = "invalid_credentials"


class AccountNotFound(AccountError):
    code = "account_not_found"


class ConsentRequired(AccountError):
    """Falta alguna aceptación obligatoria al registrarse."""
    code = "consent_required"


class GuardianRequired(AccountError):
    """Falta (o no sirve) el correo del representante legal de un menor de 15."""
    code = "guardian_email_required"


class GuardianPending(AccountError):
    """La cuenta espera la confirmación de su representante legal."""
    code = "guardian_pending"


class GuardianTokenInvalid(AccountError):
    """Enlace de confirmación desconocido, vencido o ya usado."""
    code = "guardian_token_invalid"


class GuardianResendTooSoon(AccountError):
    """Se pidió reenviar el correo al representante demasiado pronto."""
    code = "guardian_resend_wait"


class GuardianMailUnavailable(AccountError):
    """No se pudo enviar el correo al representante (sin SMTP o fallo)."""
    code = "guardian_mail_unavailable"


class TermsOutdated(AccountError):
    """El cliente mostró otra versión de los textos legales que la vigente."""
    code = "terms_outdated"


# ── Funciones puras ──────────────────────────────────────────────────────────

def normalize_email(email: Any) -> str:
    """Devuelve el email en minúsculas y validado, o lanza InvalidEmail."""
    if not isinstance(email, str):
        raise InvalidEmail("El email es obligatorio")
    value = unicodedata.normalize("NFKC", email).strip().lower()
    if not value or len(value) > MAX_EMAIL_LENGTH:
        raise InvalidEmail("Email inválido")
    if not value.isascii() or not _EMAIL_RE.match(value):
        raise InvalidEmail("Email inválido")
    local = value.split("@", 1)[0]
    if len(local) > MAX_EMAIL_LOCAL_LENGTH or ".." in value or local.startswith(".") or local.endswith("."):
        raise InvalidEmail("Email inválido")
    return value


def _normalize_password(password: Any) -> str:
    if not isinstance(password, str):
        raise WeakPassword("La contraseña es obligatoria")
    return unicodedata.normalize("NFKC", password)


def validate_password(password: Any, email: Optional[str] = None) -> str:
    """Valida la fortaleza mínima y devuelve la contraseña normalizada."""
    pw = _normalize_password(password)
    if len(pw) < MIN_PASSWORD_LENGTH:
        raise WeakPassword(f"La contraseña debe tener al menos {MIN_PASSWORD_LENGTH} caracteres")
    if len(pw) > MAX_PASSWORD_LENGTH:
        raise WeakPassword(f"La contraseña no puede superar {MAX_PASSWORD_LENGTH} caracteres")
    if len(set(pw)) < 4:
        raise WeakPassword("La contraseña es demasiado repetitiva")
    if pw.lower() in _COMMON_PASSWORDS:
        raise WeakPassword("La contraseña es demasiado común")
    if email:
        if pw.lower() == email.lower():
            raise WeakPassword("La contraseña no puede ser tu email")
        local = email.split("@", 1)[0].lower()
        if len(local) >= 4 and local in pw.lower():
            raise WeakPassword("La contraseña no puede contener tu email")
    return pw


def parse_birth_date(value: Any, today: Optional[date] = None) -> date:
    """Acepta date o 'YYYY-MM-DD'. Lanza InvalidBirthDate si no es plausible."""
    today = today or date.today()
    if isinstance(value, datetime):
        value = value.date()
    if isinstance(value, str):
        try:
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value.strip()):
                raise ValueError
            value = date.fromisoformat(value.strip())
        except ValueError:
            raise InvalidBirthDate("Fecha de nacimiento inválida (usa AAAA-MM-DD)")
    if not isinstance(value, date):
        raise InvalidBirthDate("Fecha de nacimiento inválida")
    if value > today:
        raise InvalidBirthDate("La fecha de nacimiento no puede ser futura")
    if compute_age(value, today) > MAX_AGE:
        raise InvalidBirthDate("Fecha de nacimiento inválida")
    return value


def compute_age(birth: date, today: date) -> int:
    """Edad cumplida con la fecha completa (día y mes incluidos)."""
    years = today.year - birth.year
    if (today.month, today.day) < (birth.month, birth.day):
        years -= 1
    return years


def age_band(age: int) -> str:
    """'under_13' | 'minor' (13-14) | 'minor_basic' (15-17) | 'adult' (18+)."""
    if age < MIN_AGE:
        return "under_13"
    if age < 15:
        return "minor"
    if age < 18:
        return "minor_basic"
    return "adult"


def sanitize_display_name(value: Any) -> Optional[str]:
    """
    Nombre para mostrar: solo letras (cualquier idioma), espacios,
    apóstrofo, guion y punto; 1-40 caracteres. Cadena vacía o None -> None
    (sin nombre). Cualquier otro carácter se RECHAZA (no se limpia en
    silencio): el nombre llega al prompt de Ollama, así que no debe poder
    llevar símbolos ni instrucciones con formato.
    """
    if value is None:
        return None
    if not isinstance(value, str):
        raise InvalidDisplayName("Nombre inválido")
    normalized = unicodedata.normalize("NFKC", value)
    # Saltos de línea, tabuladores y caracteres de control se RECHAZAN
    # (no se aplanan): un nombre multilínea es una forma clásica de
    # intentar colar instrucciones en el prompt.
    for ch in normalized:
        if (ch.isspace() and ch != " ") or unicodedata.category(ch).startswith("C"):
            raise InvalidDisplayName("El nombre no puede tener saltos de línea ni caracteres de control")
    name = " ".join(normalized.split())
    if not name:
        return None
    if len(name) > DISPLAY_NAME_MAX:
        raise InvalidDisplayName(f"El nombre no puede superar {DISPLAY_NAME_MAX} caracteres")
    if not any(ch.isalpha() for ch in name):
        raise InvalidDisplayName("El nombre debe contener letras")
    for ch in name:
        if not (ch.isalpha() or ch in " '-."):
            raise InvalidDisplayName("El nombre solo puede tener letras, espacios, apóstrofo, guion y punto")
    return name


def validate_consent(band: str, consent: Any) -> Dict[str, Any]:
    """
    Valida las aceptaciones de quien se registra y devuelve lo que se guarda.
    Estricto: solo el booleano JSON `true` vale (nada de "true", 1 ni "on").
    Para 13-14 años estas aceptaciones son las del propio menor; el
    consentimiento que cuenta es el del representante (confirm_guardian).
    """
    if not isinstance(consent, dict):
        raise ConsentRequired("Debes aceptar los Términos y la Política de Privacidad")
    if "version" not in consent:
        raise ConsentRequired("Debes aceptar los Términos y la Política de Privacidad")
    if consent.get("version") != TERMS_VERSION:
        raise TermsOutdated(
            "Los textos legales cambiaron. Recarga la página y léelos de nuevo antes de aceptar"
        )
    if consent.get("terms") is not True:
        raise ConsentRequired("Debes aceptar los Términos y la Política de Privacidad")
    if consent.get("sensitive") is not True:
        raise ConsentRequired(
            "Debes autorizar de forma expresa el tratamiento de tus datos de salud y estado emocional"
        )
    return {"terms_version": TERMS_VERSION, "guardian_declared": False}


def _guardian_digest(token: str) -> str:
    return hashlib.sha256(f"guardian:{token}".encode("utf-8")).hexdigest()


def _b64(raw: bytes) -> str:
    return base64.b64encode(raw).decode("ascii")


def hash_password(password: str, iterations: int = PBKDF2_ITERATIONS) -> str:
    """Hash versionado 'pbkdf2_sha256$iteraciones$sal$hash'."""
    salt = os.urandom(SALT_BYTES)
    key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return f"{HASH_SCHEME}${iterations}${_b64(salt)}${_b64(key)}"


def verify_hash(password: str, stored: str) -> Tuple[bool, int]:
    """
    Verifica una contraseña (ya normalizada) contra un hash versionado.
    Devuelve (coincide, iteraciones_del_hash). Fail-closed ante formato roto.
    """
    try:
        scheme, iters_s, salt_b64, key_b64 = stored.split("$")
        if scheme != HASH_SCHEME:
            return False, 0
        iterations = int(iters_s)
        if not (MIN_ITERATIONS_ACCEPTED <= iterations <= MAX_ITERATIONS_ACCEPTED):
            return False, 0
        salt = base64.b64decode(salt_b64, validate=True)
        expected = base64.b64decode(key_b64, validate=True)
        if not salt or not expected:
            return False, 0
        derived = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
        return hmac.compare_digest(derived, expected), iterations
    except (ValueError, TypeError, AttributeError):
        return False, 0


def generate_recovery_code() -> str:
    """Código de recuperación 'XXXX-XXXX-XXXX-XXXX-XXXX' (100 bits)."""
    raw = "".join(secrets.choice(RECOVERY_ALPHABET) for _ in range(RECOVERY_LENGTH))
    return "-".join(raw[i:i + 4] for i in range(0, RECOVERY_LENGTH, 4))


def _normalize_recovery_code(code: Any) -> str:
    if not isinstance(code, str):
        return ""
    return re.sub(r"[^A-Z0-9]", "", code.upper())


def _recovery_digest(user_id: str, code: str) -> str:
    return hashlib.sha256(f"{user_id}:{code}".encode("utf-8")).hexdigest()


# ── Almacén ──────────────────────────────────────────────────────────────────

_SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts (
    id                    TEXT PRIMARY KEY,
    email                 TEXT NOT NULL UNIQUE,
    password_hash         TEXT NOT NULL,
    display_name          TEXT,
    birth_date            TEXT NOT NULL,
    session_version       INTEGER NOT NULL DEFAULT 1,
    failed_attempts       INTEGER NOT NULL DEFAULT 0,
    locked_until          REAL NOT NULL DEFAULT 0,
    recovery_hash         TEXT NOT NULL,
    recovery_failed       INTEGER NOT NULL DEFAULT 0,
    recovery_locked_until REAL NOT NULL DEFAULT 0,
    created_at            REAL NOT NULL,
    updated_at            REAL NOT NULL,
    last_login_at         REAL,
    terms_version         TEXT,
    terms_accepted_at     REAL,
    sensitive_consent_at  REAL,
    guardian_declared     INTEGER NOT NULL DEFAULT 0,
    guardian_email        TEXT,
    guardian_token_hash   TEXT,
    guardian_token_expires REAL,
    guardian_sent_at      REAL,
    guardian_confirmed_at REAL,
    guardian_terms_version TEXT
);
CREATE TABLE IF NOT EXISTS external_identities (
    provider   TEXT NOT NULL,
    subject    TEXT NOT NULL,
    account_id TEXT NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    created_at REAL NOT NULL,
    PRIMARY KEY (provider, subject)
);
"""


class AccountStore:
    """
    Cuentas de usuario en SQLite (WAL). Una conexión persistente con lock,
    igual que el resto de almacenes del proyecto. El cálculo de hashes
    (lento a propósito) se hace FUERA del lock para no bloquear a los
    demás hilos.
    """

    def __init__(
        self,
        db_path,
        pbkdf2_iterations: int = PBKDF2_ITERATIONS,
        clock: Callable[[], float] = time.time,
        today: Callable[[], date] = date.today,
    ) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.iterations = int(pbkdf2_iterations)
        self._now = clock
        self._today = today
        self._lock = threading.RLock()
        self._conn: Optional[sqlite3.Connection] = sqlite3.connect(
            str(self.db_path), check_same_thread=False, timeout=10
        )
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=NORMAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
            self._conn.executescript(_SCHEMA)
            self._migrate()
            self._conn.commit()
        self._dummy_hash = hash_password(_DUMMY_PASSWORD, self.iterations)

    # ── utilidades internas ──────────────────────────────────────────────

    # Columnas añadidas después de la primera versión del esquema: las bases
    # ya creadas se amplían solas al abrirlas (sin perder cuentas).
    _ADDED_COLUMNS = (
        ("terms_version", "TEXT"),
        ("terms_accepted_at", "REAL"),
        ("sensitive_consent_at", "REAL"),
        ("guardian_declared", "INTEGER NOT NULL DEFAULT 0"),
        ("guardian_email", "TEXT"),
        ("guardian_token_hash", "TEXT"),
        ("guardian_token_expires", "REAL"),
        ("guardian_sent_at", "REAL"),
        ("guardian_confirmed_at", "REAL"),
        ("guardian_terms_version", "TEXT"),
    )

    def _migrate(self) -> None:
        existing = {r["name"] for r in self._conn.execute("PRAGMA table_info(accounts)")}
        for name, decl in self._ADDED_COLUMNS:
            if name not in existing:
                self._conn.execute(f"ALTER TABLE accounts ADD COLUMN {name} {decl}")

    def _row(self, where: str, params: tuple) -> Optional[sqlite3.Row]:
        with self._lock:
            return self._conn.execute(
                f"SELECT * FROM accounts WHERE {where}", params
            ).fetchone()

    def _guardian_pending(self, row: sqlite3.Row) -> bool:
        """13-14 años sin confirmación del representante. Al cumplir 15 deja
        de aplicar (consentimiento directo)."""
        birth = date.fromisoformat(row["birth_date"])
        band = age_band(compute_age(birth, self._today()))
        return band == "minor" and row["guardian_confirmed_at"] is None

    def _profile(self, row: sqlite3.Row) -> Dict[str, Any]:
        birth = date.fromisoformat(row["birth_date"])
        return {
            "user_id": row["id"],
            "email": row["email"],
            "display_name": row["display_name"],
            "age_band": age_band(compute_age(birth, self._today())),
            "created_at": row["created_at"],
            "guardian_pending": self._guardian_pending(row),
        }

    def _burn_hash_time(self) -> None:
        """Gasta el mismo CPU que una verificación real (anti-enumeración)."""
        verify_hash(_DUMMY_PASSWORD + "x", self._dummy_hash)

    # ── registro ─────────────────────────────────────────────────────────

    def register(
        self,
        user_id: str,
        email: str,
        password: str,
        birth_date: Any,
        display_name: Optional[str] = None,
        consent: Optional[Dict[str, Any]] = None,
        require_consent: bool = False,
        guardian_email: Optional[str] = None,
    ) -> Tuple[Dict[str, Any], str]:
        """
        Crea una cuenta. `user_id` es el uuid de la sesión anónima actual.
        Devuelve (perfil, código_de_recuperación). El código solo se
        entrega aquí: guardarlo es responsabilidad de la persona.

        `consent`: aceptaciones (ver validate_consent). Con
        `require_consent=True` (lo que usa la API) faltar alguna es un
        error; sin él, solo se valida y guarda si se proporciona.

        `guardian_email`: correo del representante legal. Obligatorio para
        13-14 años cuando `require_consent=True`; la cuenta queda PENDIENTE
        (sin login) hasta confirm_guardian(). Para otras edades se ignora
        y no se guarda. El token se emite aparte (issue_guardian_token).
        """
        if not isinstance(user_id, str) or not _UUID_RE.match(user_id):
            raise IdentityInUse("Identificador de sesión inválido")
        email_n = normalize_email(email)
        pw = validate_password(password, email_n)
        birth = parse_birth_date(birth_date, self._today())
        band = age_band(compute_age(birth, self._today()))
        if band == "under_13":
            raise UnderageError(f"Debes tener al menos {MIN_AGE} años para crear una cuenta")
        name = sanitize_display_name(display_name)
        record = validate_consent(band, consent) if (require_consent or consent is not None) else None
        guardian_n = None
        if band == "minor":
            if guardian_email not in (None, ""):
                guardian_n = self._clean_guardian_email(guardian_email, email_n)
            elif require_consent:
                raise GuardianRequired(
                    "Con 13 o 14 años necesitas el correo de tu madre, padre o representante legal "
                    "para que confirme tu cuenta"
                )

        pw_hash = hash_password(pw, self.iterations)
        code = generate_recovery_code()
        code_digest = _recovery_digest(user_id, _normalize_recovery_code(code))
        now = self._now()

        with self._lock:
            try:
                self._conn.execute(
                    "INSERT INTO accounts (id, email, password_hash, display_name,"
                    " birth_date, recovery_hash, created_at, updated_at,"
                    " terms_version, terms_accepted_at, sensitive_consent_at, guardian_declared,"
                    " guardian_email)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (user_id, email_n, pw_hash, name, birth.isoformat(),
                     code_digest, now, now,
                     record["terms_version"] if record else None,
                     now if record else None,
                     now if record else None,
                     1 if (record and record["guardian_declared"]) else 0,
                     guardian_n),
                )
                self._conn.commit()
            except sqlite3.IntegrityError as e:
                self._conn.rollback()
                if "accounts.email" in str(e):
                    raise EmailTaken("Ya existe una cuenta con ese email")
                raise IdentityInUse("Esta sesión ya tiene una cuenta")
            row = self._row("id = ?", (user_id,))
        return self._profile(row), code

    # ── login ────────────────────────────────────────────────────────────

    def authenticate(
        self, email: Any, password: Any, allow_pending: bool = False
    ) -> Tuple[Dict[str, Any], int]:
        """
        Devuelve (perfil, session_version) o lanza InvalidCredentials.
        Email inexistente, contraseña incorrecta y cuenta bloqueada son
        indistinguibles desde fuera. Con la contraseña correcta, una cuenta
        de 13-14 años sin confirmar lanza GuardianPending (salvo
        `allow_pending`, que usa el reenvío del correo al representante).
        """
        try:
            email_n = normalize_email(email)
            pw = _normalize_password(password)
        except AccountError:
            self._burn_hash_time()
            raise InvalidCredentials("Credenciales incorrectas")

        if len(pw) > MAX_PASSWORD_LENGTH:
            self._burn_hash_time()
            raise InvalidCredentials("Credenciales incorrectas")

        row = self._row("email = ?", (email_n,))
        now = self._now()
        if row is None or row["locked_until"] > now:
            self._burn_hash_time()
            raise InvalidCredentials("Credenciales incorrectas")

        ok, stored_iters = verify_hash(pw, row["password_hash"])
        uid = row["id"]
        with self._lock:
            if not ok:
                fails = (self._conn.execute(
                    "SELECT failed_attempts FROM accounts WHERE id = ?", (uid,)
                ).fetchone() or {"failed_attempts": 0})["failed_attempts"] + 1
                if fails >= MAX_FAILED_ATTEMPTS:
                    self._conn.execute(
                        "UPDATE accounts SET failed_attempts = 0, locked_until = ? WHERE id = ?",
                        (now + LOCKOUT_SECONDS, uid),
                    )
                else:
                    self._conn.execute(
                        "UPDATE accounts SET failed_attempts = ? WHERE id = ?", (fails, uid)
                    )
                self._conn.commit()
                raise InvalidCredentials("Credenciales incorrectas")

        new_hash = None
        if stored_iters < self.iterations:
            new_hash = hash_password(pw, self.iterations)
        pending = self._guardian_pending(row)
        with self._lock:
            self._conn.execute(
                "UPDATE accounts SET failed_attempts = 0, locked_until = 0,"
                " last_login_at = CASE WHEN ? THEN last_login_at ELSE ? END,"
                " password_hash = COALESCE(?, password_hash)"
                " WHERE id = ?",
                (1 if pending else 0, now, new_hash, uid),
            )
            self._conn.commit()
            fresh = self._row("id = ?", (uid,))
        if pending and not allow_pending:
            raise GuardianPending(
                "Tu cuenta espera la confirmación de tu madre, padre o representante legal"
            )
        return self._profile(fresh), int(fresh["session_version"])

    # ── lectura ──────────────────────────────────────────────────────────

    def exists(self, user_id: str) -> bool:
        return self._row("id = ?", (user_id,)) is not None

    def get_profile(self, user_id: str) -> Optional[Dict[str, Any]]:
        row = self._row("id = ?", (user_id,))
        return self._profile(row) if row else None

    def get_session_version(self, user_id: str) -> Optional[int]:
        row = self._row("id = ?", (user_id,))
        return int(row["session_version"]) if row else None

    def count(self) -> int:
        with self._lock:
            return int(self._conn.execute("SELECT COUNT(*) FROM accounts").fetchone()[0])

    # ── perfil ───────────────────────────────────────────────────────────

    def update_profile(self, user_id: str, display_name: Any) -> Dict[str, Any]:
        """Actualiza el nombre para mostrar (None o '' lo borra)."""
        name = sanitize_display_name(display_name)
        with self._lock:
            cur = self._conn.execute(
                "UPDATE accounts SET display_name = ?, updated_at = ? WHERE id = ?",
                (name, self._now(), user_id),
            )
            self._conn.commit()
            if cur.rowcount == 0:
                raise AccountNotFound("Cuenta no encontrada")
            return self._profile(self._row("id = ?", (user_id,)))

    # ── consentimiento y exportación (derecho de acceso) ─────────────────

    @staticmethod
    def _iso(ts: Optional[float]) -> Optional[str]:
        if ts is None:
            return None
        return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()

    def get_consent(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Consentimiento registrado de la cuenta, o None si no existe o no
        se registró (cuentas anteriores a esta función)."""
        row = self._row("id = ?", (user_id,))
        if row is None or row["terms_version"] is None:
            return None
        return {
            "terms_version": row["terms_version"],
            "terms_accepted_at": self._iso(row["terms_accepted_at"]),
            "sensitive_consent_at": self._iso(row["sensitive_consent_at"]),
            "guardian_declared": bool(row["guardian_declared"]),
            "guardian_confirmed_at": self._iso(row["guardian_confirmed_at"]),
            "guardian_terms_version": row["guardian_terms_version"],
        }

    def export_account(self, user_id: str, password: Any) -> Dict[str, Any]:
        """
        Todos los datos que la cuenta guarda de su titular (derecho de
        acceso y portabilidad). Exige la contraseña: es una descarga
        sensible. Es el ÚNICO sitio por el que sale la fecha de nacimiento,
        y solo hacia su dueño. Nunca incluye hashes ni el código.
        """
        row = self._check_current_password(user_id, password)
        return {
            "user_id": row["id"],
            "email": row["email"],
            "display_name": row["display_name"],
            "birth_date": row["birth_date"],
            "age_band": age_band(compute_age(date.fromisoformat(row["birth_date"]), self._today())),
            "created_at": self._iso(row["created_at"]),
            "last_login_at": self._iso(row["last_login_at"]),
            "consent": self.get_consent(user_id),
            "guardian": {
                "email": row["guardian_email"],
                "confirmed_at": self._iso(row["guardian_confirmed_at"]),
            } if row["guardian_email"] else None,
        }

    # ── representante legal (13-14 años) ─────────────────────────────────

    @staticmethod
    def _clean_guardian_email(guardian_email: Any, own_email: str) -> str:
        try:
            g = normalize_email(guardian_email)
        except InvalidEmail:
            raise GuardianRequired("El correo del representante no es válido")
        if g == own_email:
            raise GuardianRequired(
                "El correo del representante debe ser distinto del tuyo: lo recibe otra persona"
            )
        return g

    def issue_guardian_token(
        self, user_id: str, guardian_email: Any = None
    ) -> Tuple[str, str]:
        """
        Emite un enlace de confirmación NUEVO (el anterior deja de servir) para
        una cuenta pendiente. Devuelve (correo_del_representante, token); el
        token solo existe aquí: en la base queda su hash. `guardian_email`
        corrige o fija el correo (cuentas antiguas sin él, o un error al
        escribirlo). Respeta una espera entre envíos.
        """
        now = self._now()
        with self._lock:
            row = self._row("id = ?", (user_id,))
            if row is None:
                raise AccountNotFound("Cuenta no encontrada")
            if not self._guardian_pending(row):
                raise GuardianTokenInvalid("Esta cuenta no necesita confirmación del representante")
            sent = row["guardian_sent_at"]
            if sent is not None and now - sent < GUARDIAN_RESEND_COOLDOWN_SECONDS:
                raise GuardianResendTooSoon(
                    "Ya se envió un correo hace poco. Espera unos minutos antes de pedir otro"
                )
            target = row["guardian_email"]
            if guardian_email not in (None, ""):
                target = self._clean_guardian_email(guardian_email, row["email"])
            if not target:
                raise GuardianRequired("Indica el correo de tu madre, padre o representante legal")
            token = secrets.token_urlsafe(32)
            self._conn.execute(
                "UPDATE accounts SET guardian_email = ?, guardian_token_hash = ?,"
                " guardian_token_expires = ?, guardian_sent_at = ?, updated_at = ? WHERE id = ?",
                (target, _guardian_digest(token), now + GUARDIAN_TOKEN_TTL_SECONDS, now, now, user_id),
            )
            self._conn.commit()
        return target, token

    def release_guardian_cooldown(self, user_id: str) -> None:
        """Quita la espera de reenvío (se usa si el correo NO pudo enviarse:
        no tiene sentido castigar al usuario por un fallo del servidor)."""
        with self._lock:
            self._conn.execute(
                "UPDATE accounts SET guardian_sent_at = NULL WHERE id = ?", (user_id,)
            )
            self._conn.commit()

    def confirm_guardian(self, token: Any, consent: Any) -> bool:
        """
        El representante legal confirma desde el enlace de su correo. Exige que
        acepte Términos, Privacidad y el tratamiento de datos sensibles de la
        persona menor. El token es de un solo uso y vence. Mismo error para
        token desconocido, vencido o ya usado.
        """
        if not isinstance(token, str) or not _GUARDIAN_TOKEN_RE.match(token):
            raise GuardianTokenInvalid("El enlace no es válido o ya venció")
        record = validate_consent("adult", consent)   # mismas reglas de aceptación
        digest = _guardian_digest(token)
        now = self._now()
        with self._lock:
            row = self._conn.execute(
                "SELECT id, guardian_token_expires FROM accounts WHERE guardian_token_hash = ?",
                (digest,),
            ).fetchone()
            if row is None or (row["guardian_token_expires"] or 0) < now:
                raise GuardianTokenInvalid("El enlace no es válido o ya venció")
            self._conn.execute(
                "UPDATE accounts SET guardian_confirmed_at = ?, guardian_terms_version = ?,"
                " guardian_token_hash = NULL, guardian_token_expires = NULL, updated_at = ?"
                " WHERE id = ?",
                (now, record["terms_version"], now, row["id"]),
            )
            self._conn.commit()
        return True

    def abort_pending(self, user_id: str) -> bool:
        """Borra una cuenta que quedó pendiente porque el correo al
        representante no pudo enviarse (no se deja una cuenta inalcanzable).
        Solo actúa sobre cuentas pendientes."""
        with self._lock:
            row = self._row("id = ?", (user_id,))
            if row is None or not self._guardian_pending(row):
                return False
            self._conn.execute("DELETE FROM accounts WHERE id = ?", (user_id,))
            self._conn.commit()
            return True

    def prune_unconfirmed(self, days: float = GUARDIAN_PENDING_PRUNE_DAYS) -> list:
        """Borra las cuentas de 13-14 años que siguen sin confirmar tras
        `days` días. Devuelve los user_id borrados (para limpiar sus carpetas)."""
        if days <= 0:
            return []
        cutoff = self._now() - days * 86400
        removed = []
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM accounts WHERE guardian_confirmed_at IS NULL AND created_at < ?",
                (cutoff,),
            ).fetchall()
            for row in rows:
                if self._guardian_pending(row):
                    self._conn.execute("DELETE FROM accounts WHERE id = ?", (row["id"],))
                    removed.append(row["id"])
            self._conn.commit()
        return removed

    # ── contraseña ───────────────────────────────────────────────────────

    def _check_current_password(self, user_id: str, password: Any) -> sqlite3.Row:
        """Verifica la contraseña actual contando fallos (anti fuerza bruta)."""
        row = self._row("id = ?", (user_id,))
        if row is None:
            self._burn_hash_time()
            raise InvalidCredentials("Credenciales incorrectas")
        try:
            pw = _normalize_password(password)
        except AccountError:
            self._burn_hash_time()
            raise InvalidCredentials("Credenciales incorrectas")
        now = self._now()
        if row["locked_until"] > now or len(pw) > MAX_PASSWORD_LENGTH:
            self._burn_hash_time()
            raise InvalidCredentials("Credenciales incorrectas")
        ok, _ = verify_hash(pw, row["password_hash"])
        if not ok:
            with self._lock:
                fails = row["failed_attempts"] + 1
                if fails >= MAX_FAILED_ATTEMPTS:
                    self._conn.execute(
                        "UPDATE accounts SET failed_attempts = 0, locked_until = ? WHERE id = ?",
                        (now + LOCKOUT_SECONDS, user_id),
                    )
                else:
                    self._conn.execute(
                        "UPDATE accounts SET failed_attempts = ? WHERE id = ?", (fails, user_id)
                    )
                self._conn.commit()
            raise InvalidCredentials("Credenciales incorrectas")
        return row

    def change_password(self, user_id: str, current_password: Any, new_password: Any) -> int:
        """
        Cambia la contraseña. Devuelve la nueva session_version (la sesión
        actual debe adoptarla; las de otros dispositivos quedan invalidadas).
        """
        row = self._check_current_password(user_id, current_password)
        new_pw = validate_password(new_password, row["email"])
        if hmac.compare_digest(
            new_pw.encode("utf-8"), _normalize_password(current_password).encode("utf-8")
        ):
            raise WeakPassword("La contraseña nueva debe ser distinta de la actual")
        new_hash = hash_password(new_pw, self.iterations)
        with self._lock:
            self._conn.execute(
                "UPDATE accounts SET password_hash = ?, session_version = session_version + 1,"
                " failed_attempts = 0, locked_until = 0, updated_at = ? WHERE id = ?",
                (new_hash, self._now(), user_id),
            )
            self._conn.commit()
            return int(self._row("id = ?", (user_id,))["session_version"])

    def recover(
        self, email: Any, recovery_code: Any, new_password: Any
    ) -> Tuple[Dict[str, Any], str, int]:
        """
        Restablece la contraseña con el código de recuperación. Devuelve
        (perfil, NUEVO_código, session_version). El código usado deja de
        servir. Fallos repetidos bloquean la recuperación 15 minutos.
        """
        try:
            email_n = normalize_email(email)
        except AccountError:
            self._burn_hash_time()
            raise InvalidCredentials("Datos de recuperación incorrectos")
        row = self._row("email = ?", (email_n,))
        now = self._now()
        if row is None or row["recovery_locked_until"] > now:
            self._burn_hash_time()
            raise InvalidCredentials("Datos de recuperación incorrectos")

        uid = row["id"]
        digest = _recovery_digest(uid, _normalize_recovery_code(recovery_code))
        if not hmac.compare_digest(digest, row["recovery_hash"]):
            with self._lock:
                fails = row["recovery_failed"] + 1
                if fails >= MAX_FAILED_ATTEMPTS:
                    self._conn.execute(
                        "UPDATE accounts SET recovery_failed = 0, recovery_locked_until = ?"
                        " WHERE id = ?", (now + LOCKOUT_SECONDS, uid),
                    )
                else:
                    self._conn.execute(
                        "UPDATE accounts SET recovery_failed = ? WHERE id = ?", (fails, uid)
                    )
                self._conn.commit()
            raise InvalidCredentials("Datos de recuperación incorrectos")

        # El código es correcto: ahora sí se valida la contraseña nueva.
        # Si es débil se lanza WeakPassword SIN gastar el código.
        new_pw = validate_password(new_password, email_n)
        new_hash = hash_password(new_pw, self.iterations)
        new_code = generate_recovery_code()
        new_digest = _recovery_digest(uid, _normalize_recovery_code(new_code))
        with self._lock:
            self._conn.execute(
                "UPDATE accounts SET password_hash = ?, recovery_hash = ?,"
                " session_version = session_version + 1, failed_attempts = 0, locked_until = 0,"
                " recovery_failed = 0, recovery_locked_until = 0, updated_at = ? WHERE id = ?",
                (new_hash, new_digest, now, uid),
            )
            self._conn.commit()
            fresh = self._row("id = ?", (uid,))
        return self._profile(fresh), new_code, int(fresh["session_version"])

    # ── borrado ──────────────────────────────────────────────────────────

    def delete_account(self, user_id: str, password: Any) -> bool:
        """Borra la cuenta (derecho de supresión). Exige la contraseña."""
        self._check_current_password(user_id, password)
        with self._lock:
            cur = self._conn.execute("DELETE FROM accounts WHERE id = ?", (user_id,))
            self._conn.commit()
            return cur.rowcount > 0

    # ── identidades externas (ecosistema; aún sin uso) ───────────────────

    def link_external(self, user_id: str, provider: str, subject: str) -> None:
        if not (isinstance(provider, str) and isinstance(subject, str) and provider and subject):
            raise IdentityInUse("Identidad externa inválida")
        with self._lock:
            if not self._row("id = ?", (user_id,)):
                raise AccountNotFound("Cuenta no encontrada")
            try:
                self._conn.execute(
                    "INSERT INTO external_identities (provider, subject, account_id, created_at)"
                    " VALUES (?, ?, ?, ?)",
                    (provider.strip().lower(), subject, user_id, self._now()),
                )
                self._conn.commit()
            except sqlite3.IntegrityError:
                self._conn.rollback()
                raise IdentityInUse("Esa identidad externa ya está enlazada")

    def find_by_external(self, provider: str, subject: str) -> Optional[str]:
        with self._lock:
            row = self._conn.execute(
                "SELECT account_id FROM external_identities WHERE provider = ? AND subject = ?",
                (str(provider).strip().lower(), str(subject)),
            ).fetchone()
        return row["account_id"] if row else None

    # ── cierre ───────────────────────────────────────────────────────────

    def close(self) -> None:
        with self._lock:
            if self._conn is not None:
                try:
                    self._conn.commit()
                    self._conn.close()
                finally:
                    self._conn = None