"""
* UBICACIÓN: OmniaMentis/src/api/main_flask.py
* PROPÓSITO: API REST con Flask — orquesta ética, empatía, memoria,
*            crecimiento de consciencia, router de módulos, Ollama y
*            autenticación del panel del Fons + entrega asíncrona de
*            resoluciones al usuario final.
* DEPENDENCIAS: flask, flask-cors, requests (ver requirements.txt);
*            core.auth.fons_auth (stdlib only)
* CREADO: 2026-06-14
* ÚLTIMA MODIFICACIÓN: 2026-10-14
*
* CAMBIO 2026-10-14 -- RESOLUCIONES DEL ESPECIALISTA:
*   (1) Edad: 13-14 años exigen confirmación VERIFICABLE del representante
*   legal (enlace único enviado a su correo; POST /api/account/guardian/confirm
*   y /guardian/resend). La cuenta nace pendiente y no inicia sesión hasta
*   entonces. Se eliminó la casilla declarativa; 15-17 años consienten solos.
*   Sin SMTP el registro de 13-14 años responde 503 (falla cerrado).
*   (2) Riesgo crítico (autolesión, violencia, violencia sexual, seguridad
*   infantil): la respuesta con ECU 911 y la línea 171 opción 6 se entrega al
*   instante (no espera al Fons) y el modelo no genera nada.
*   (3) Retención: los registros éticos se anonimizan a los 180 días
*   (ETHICS_RETENTION_DAYS); las cuentas de 13-14 años sin confirmar se
*   borran a los 30 días. Corre al arrancar y cada hora.
*   (4) Cookie de sesión: 30 días para visitantes anónimos (desde su última
*   visita) y 365 para cuentas con sesión iniciada.
*
* CAMBIO 2026-10-11 (b) -- CUMPLIMIENTO DE PRIVACIDAD:
*   (1) El registro exige consentimiento explícito (Términos+Privacidad,
*   contenido emocional y, en menores de 18, declaración del
*   representante) ligado a TERMS_VERSION; se guarda versión y fecha.
*   (2) POST /api/account/export: descarga de todos los datos de la cuenta
*   (derecho de acceso/portabilidad), con contraseña.
*   (3) Al borrar la cuenta también se anonimiza lo guardado por el sistema
*   ético (OmniaEthics.erase_user_data).
*   (4) La analítica de investigación (ResearchAnalytics) queda DESACTIVADA
*   por defecto (OMNIA_RESEARCH_LOGGING=true para activarla) y, activada,
*   no guarda el texto de los mensajes. Antes acumulaba en memoria, sin
*   límite, los mensajes de todos los usuarios mezclados.
*
* CAMBIO 2026-10-11 -- CUENTAS REALES (registro, login, perfil):
*   Nuevo core/auth/accounts.py (SQLite data/accounts.db, PBKDF2, código de
*   recuperación). Endpoints /api/account/* (register, login, logout, me,
*   profile, password, recover) y DELETE /api/account. La cuenta REUTILIZA
*   el uuid anónimo de la sesión: la consciencia y la memoria ya ganadas se
*   conservan. Es independiente del login del Fons: ninguna cuenta de
*   usuario da acceso al panel del Fons. El nombre del perfil se envía a
*   Ollama. Las cuentas nunca se purgan como "usuarios vacíos".
*   Además: los preflight CORS (OPTIONS) ya no cuentan para el límite de
*   30 peticiones/min (agotarlo daba un "Failed to fetch" opaco).
*
* CAMBIO 2026-10-10 -- CORS ROBUSTO EN LOOPBACK: _expand_loopback_origins()
*   agrega automáticamente la variante localhost <-> 127.0.0.1 de cada
*   origen configurado en CORS_ORIGINS. Un .env que solo listaba una de
*   las dos formas hacía fallar el panel del Fons ("Failed to fetch").
*
* CAMBIO 2026-10-10 -- LIMPIEZA: /health ya no muestra el modelo fijo
*   "dolphin-phi:latest" cuando Ollama no responde; muestra el modelo
*   realmente configurado (OLLAMA_MODEL). El comentario de dependencias
*   apunta a requirements.txt (requirements_web.txt se eliminó).
*
* CAMBIO 2026-10-10 -- SPACY SOLO COMPLETA, NO CONTRADICE:
*   SpaCy ya no pisa una emoción detectada por OmniaEmpathy; solo actúa
*   cuando OmniaEmpathy devuelve "neutral" y la confianza de SpaCy es
*   >= SPACY_MIN_CONFIDENCE (0.5). Ver _spacy_may_override().
*
* CAMBIO 2026-10-10 -- ENDURECIMIENTO DE SESIONES (límites y limpieza):
*   Hallazgo real: durante el fallo de cookies se acumularon ~3000
*   carpetas data/users/<id>/ (cada petición sin cookie creaba un
*   usuario nuevo con sus bases SQLite). Riesgos detectados: (1) un
*   script sin cookies podía crear usuarios sin límite y llenar el
*   disco; (2) _user_sessions nunca liberaba sesiones y cada una deja
*   2 conexiones SQLite abiertas -> agotamiento de archivos abiertos
*   en un servidor que corra días; (3) _rate_data crecía con cada IP.
*   Ahora (todo configurable por variable de entorno, 0 desactiva):
*   - MAX_NEW_USERS_PER_IP_HOUR (30): tope de usuarios NUEVOS por IP y
*     hora. Superarlo -> 429. Usuarios con cookie válida no se afectan.
*   - MAX_ACTIVE_SESSIONS (500) y SESSION_IDLE_TTL_SECONDS (1800): las
*     sesiones inactivas se guardan, cierran sus conexiones SQLite y se
*     sacan de memoria (se reconstruyen desde disco al volver). Una
*     sesión con actividad reciente (< 150 s, o sea con una petición
*     posiblemente en curso) nunca se expulsa; si no hay sitio -> 503.
*   - PRUNE_EMPTY_USERS_DAYS (7): borra carpetas de usuarios que nunca
*     conversaron (consciencia sin crecer, sin nombre) y llevan N días
*     sin actividad. Solo carpetas con nombre UUID, nunca sesiones
*     activas, y ante cualquier duda (estado ilegible) NO borra.
*   - El nombre dicho por el usuario ahora se guarda en el estado a
*     disco, para sobrevivir a la expulsión por inactividad.
*
* CAMBIO 2026-10-09 -- MODO DESARROLLO OMNIA_DEV_CONSCIOUSNESS:
*   Con consciencia ~0.05 y +0.0005 por mensaje, llegar a la Fase 2
*   (0.15) exige cientos de mensajes, así que la lógica de Fase 2
*   (sub-tipos de duelo) no se podía probar. Si la variable vale entre
*   0.05 y 1.0, las sesiones nuevas arrancan con ese nivel. Mientras
*   esté activa save_user_state() NO escribe a disco: el valor de
*   prueba nunca pisa el progreso real. Valores inválidos se ignoran.
*   También: el nombre dicho en el chat ("me llamo X") se guarda en la
*   sesión (sess["user_name"]) y se pasa a Ollama (ver ollama_client.py).
*
* CAMBIO 2026-10-08 -- COOKIE DE SESIÓN Y "SITIO" DEL NAVEGADOR:
* Hallazgo real: el nivel de consciencia mostrado por el dashboard
* era idéntico en mensajes consecutivos (0.0504, 0.0504, ...) en vez
* de crecer, y el modelo no recordaba lo dicho un mensaje antes. Causa:
* la página se abría en http://localhost:8080 pero llamaba a la API en
* http://127.0.0.1:8000 (cambio hecho para evitar la demora IPv6 de
* "localhost" en Windows). Para el navegador, localhost y 127.0.0.1
* son sitios DISTINTOS, así que la cookie de sesión (SameSite=Lax) se
* descartaba en cada fetch y cada mensaje arrancaba como un usuario
* nuevo. Los tests no lo detectan: el test_client de Flask no aplica
* reglas SameSite. Solución: el dashboard usa el mismo host con el que
* se abrió la página (ver omnia_dashboard.html v2.6) y los orígenes
* CORS por defecto incluyen 127.0.0.1.
*
* CAMBIO 2026-10-01 — threaded=True:
* El servidor de desarrollo de Flask, por defecto, atiende una sola
* petición HTTP a la vez. Con sesión por usuario esto se nota mucho
* más que antes: mientras una petición de /api/chat está en curso
* (puede tardar por el intento de conexión a Ollama), cualquier otra
* petición concurrente -- incluido el polling periódico de /health
* que hacen los dashboards -- queda en cola esperando. Si esa espera
* supera el timeout del fetch() del cliente, el navegador lo reporta
* como caído aunque el servidor esté perfectamente vivo, dando el
* patrón de "se conecta, se desconecta, se conecta" que threaded=True
* resuelve permitiendo que Flask maneje requests en paralelo.
* ESTADO: Producción
*
* CAMBIO 2026-09-21 — SESIÓN POR USUARIO (refactor crítico):
* ---------------------------------------------------------------
* ANTES: un único diccionario global _session contenía UNA
* OmniaIdentity, UNA LivingMemory, UN estado de consciencia —
* compartidos por cualquiera que llamara a la API. Dos personas
* usando el chat al mismo tiempo mezclaban su consciencia y su
* memoria entre sí. Esto hacía imposible un producto multiusuario
* real, incluida cualquier app móvil distribuida a más de una persona.
*
* AHORA: cada usuario se identifica mediante una cookie de sesión
* firmada (APP_SECRET_KEY) que Flask asigna automáticamente en su
* primera visita — SIN pedir login para el chat normal. Esa cookie da
* continuidad de identidad/memoria/consciencia entre visitas del mismo
* navegador, persistida en data/users/<user_id>/.
*
* OmniaEthics es la EXCEPCIÓN deliberada: se queda COMPARTIDA a nivel
* de proceso. El protocolo SILENS y el panel del Fons ya estaban
* diseñados para operar sobre un log compartido con user_id como campo
* dentro de cada consulta (ver request_fons_approval/check_recidivism
* en ethics.py) — separarlo por usuario rompería la vista unificada
* que El Fons necesita para moderar a todos desde un solo panel.
*
* El login real (usuario/contraseña del Fons) se queda exclusivo para
* el panel de moderación, sin cambios — no se mezcla con la cookie de
* sesión del usuario final, son dos mecanismos de identidad distintos
* a propósito.
*
* EFECTO SECUNDARIO POSITIVO: get_chat_resolution() ahora recupera la
* identidad del usuario REAL dueño de la consulta (vía el campo
* user_id guardado en la consulta) para generar la respuesta resuelta,
* en vez de usar la consciencia global que hubiera en ese instante —
* antes esto podía ser inconsistente si otra persona había usado el
* chat mientras la consulta esperaba revisión del Fons.
*
* PENDIENTE TRAS ESTE CAMBIO (no incluido en este archivo):
*   1. Agregar APP_SECRET_KEY a tu .env (ver instrucciones al final).
*   2. Las interfaces HTML (omnia_dashboard.html) deben enviar
*      `credentials: 'include'` en cada fetch() para que el navegador
*      mande la cookie de sesión — sin eso, cada request parecerá un
*      usuario nuevo. No modificado en este archivo (es un cambio de
*      frontend, no de backend).
*   3. CORS_ORIGINS debe listar el/los orígenes reales del frontend
*      (no se puede usar "*" junto con cookies — el navegador lo
*      rechaza). Ver env.example actualizado.
*
* EQUIVALENCIAS con main_web.py (FastAPI):
*   POST /api/chat          → misma lógica, ahora por usuario
*   GET  /api/consciousness → mismo endpoint, ahora por usuario
*   GET  /api/memory/echoes → mismo endpoint, ahora por usuario
*   GET  /health            → ya no expone una "consciencia" única
*                              (no tendría sentido con multiusuario);
*                              expone active_sessions en su lugar
*   GET  /                  → root
*
* INICIAR: python src/api/main_flask.py
*          O usar: iniciar_flask.bat
"""

import sys
import os
import json
import time
import uuid
import logging
import secrets
import re
import shutil
import threading
from pathlib import Path
from urllib.parse import urlsplit
from datetime import datetime, timedelta, timezone
from functools import wraps
from typing import Optional, Dict, Any

# ==================== PATH SETUP ====================
PROJECT_ROOT = Path(__file__).parent.parent.parent
SRC_PATH = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_PATH))

from flask import Flask, request, jsonify, Response, session, has_request_context
from flask.sessions import SecureCookieSessionInterface
from flask_cors import CORS

# ==================== IMPORTS OMNIA ====================
from core.essence.identity import OmniaIdentity
from core.essence.ethics import OmniaEthics
from core.mind.empathy import OmniaEmpathy
from core.mind.memory_core import LivingMemory
from core.consciousness.growth_engine import ConsciousnessGrowthEngine
from core.logging.logger_setup import get_logger, setup_logging
from core.llm.ollama_client import OllamaClient, OllamaUnavailableError
from core.mind.spacy_intent import SpaCyIntentClassifier
from dotenv import load_dotenv
from core.auth.fons_auth import verify_password, verify_session_token, create_session_token
from core.auth.accounts import (
    TERMS_VERSION,
    AccountStore, AccountError, InvalidEmail, WeakPassword, EmailTaken,
    IdentityInUse, InvalidBirthDate, UnderageError, InvalidDisplayName,
    InvalidCredentials, AccountNotFound, ConsentRequired, TermsOutdated,
    GuardianRequired, GuardianPending, GuardianTokenInvalid,
    GuardianResendTooSoon, GuardianMailUnavailable,
)
from core.auth import guardian_mail
from living_memory.gestation_diary import GestationDiary
from analytics.research_analytics import ResearchAnalytics
from router.integration import route_or_none, get_registered_modules

# ==================== LOGGING ====================
setup_logging(log_dir=PROJECT_ROOT / "logs", level=logging.INFO, console=True)
logger = get_logger("api_flask")

# ==================== VARIABLES DE ENTORNO (.env) ====================
load_dotenv(PROJECT_ROOT / ".env")

# ==================== DIRECTORIO DE DATOS ====================
# OMNIA_DATA_DIR permite redirigir toda la persistencia (útil para
# tests aislados); por defecto, la carpeta data/ del proyecto, igual
# que siempre.
DATA_ROOT = Path(os.environ.get("OMNIA_DATA_DIR", PROJECT_ROOT / "data"))
USERS_DIR = DATA_ROOT / "users"
ACCOUNTS_DB = DATA_ROOT / "accounts.db"
USERS_DIR.mkdir(parents=True, exist_ok=True)

# ==================== FLASK APP ====================
app = Flask(__name__)

# ==================== CLAVE DE SESIÓN DE USUARIO ====================
# Distinta de FONS_SECRET_KEY a propósito: esta firma la cookie que
# identifica a cada usuario final del chat (no al Fons). Sin ella
# configurada, se genera una aleatoria al arrancar — funcional, pero
# todos los usuarios pierden su identidad persistente cada vez que el
# proceso se reinicia (cada deploy, por ejemplo). Para producción real
# define APP_SECRET_KEY en .env, igual que ya haces con FONS_SECRET_KEY.
APP_SECRET_KEY = os.environ.get("APP_SECRET_KEY", "")
if not APP_SECRET_KEY:
    APP_SECRET_KEY = secrets.token_hex(32)
    logger.warning(
        "⚠️  APP_SECRET_KEY no configurado. Se generó uno temporal: "
        "las sesiones de usuario (consciencia/memoria) se perderán "
        "cada vez que el servidor se reinicie. Define APP_SECRET_KEY "
        "en .env para que sean persistentes de verdad."
    )
app.secret_key = APP_SECRET_KEY
app.permanent_session_lifetime = timedelta(days=365)

ANON_COOKIE_DAYS = 30        # visitantes anónimos: desde su última visita
ACCOUNT_COOKIE_DAYS = 365    # cuentas con sesión iniciada (evita re-login diario)


class _OmniaSessionInterface(SecureCookieSessionInterface):
    """Cookie de sesión con vigencia según quién la lleva: 30 días para
    visitantes anónimos y 365 para cuentas con sesión iniciada. Una cookie
    de un año para quien nunca se registró no es "estrictamente necesaria"
    (resolución del especialista, 2026-10-14)."""

    def get_expiration_time(self, app, session):
        if not session.permanent:
            return None
        days = ACCOUNT_COOKIE_DAYS if session.get("account_id") else ANON_COOKIE_DAYS
        return datetime.now(timezone.utc) + timedelta(days=days)


app.session_interface = _OmniaSessionInterface()
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = (
    os.environ.get("SESSION_COOKIE_SECURE", "false").lower() == "true"
)

# CORS: con cookies de sesión de por medio, el origen NO puede ser "*"
# — el navegador lo rechaza silenciosamente. CORS_ORIGINS acepta una
# lista separada por comas; sin configurar, cae a localhost para dev.
# Orígenes por defecto (desarrollo local). Incluye AMBAS formas de
# loopback (localhost y 127.0.0.1): para el navegador son "sitios"
# distintos, y la cookie de sesión por usuario solo viaja si la página
# y la API comparten sitio (ver CAMBIO 2026-10-08 arriba).
DEFAULT_CORS_ORIGINS = (
    "http://localhost:3000,http://localhost:8080,"
    "http://127.0.0.1:3000,http://127.0.0.1:8080"
)


def _expand_loopback_origins(origins):
    """
    Para cada origen en localhost o 127.0.0.1 agrega la variante
    equivalente (mismo esquema y puerto). Para el navegador son orígenes
    distintos, y un CORS_ORIGINS que solo lista uno de los dos hace que
    el otro falle con "Failed to fetch" sin más pistas (ocurrió con el
    panel del Fons). Ambas formas apuntan a esta misma máquina, así que
    permitirlas juntas no amplía la superficie de ataque. Orígenes
    externos y "*" no se tocan.
    """
    expanded = []
    for origin in origins:
        if origin not in expanded:
            expanded.append(origin)
        try:
            parts = urlsplit(origin)
            host, port = parts.hostname, parts.port
        except ValueError:
            continue
        if host not in ("localhost", "127.0.0.1") or not parts.scheme:
            continue
        other = "127.0.0.1" if host == "localhost" else "localhost"
        variant = f"{parts.scheme}://{other}" + (f":{port}" if port else "")
        if variant not in expanded:
            expanded.append(variant)
    return expanded


_cors_origins_raw = os.environ.get("CORS_ORIGINS", DEFAULT_CORS_ORIGINS)
_cors_origins = _expand_loopback_origins(
    [o.strip() for o in _cors_origins_raw.split(",") if o.strip()]
)
CORS(app, supports_credentials=True, origins=_cors_origins)

# ==================== AUTENTICACIÓN DEL PANEL DEL FONS ====================
# Sin cambios respecto a la versión anterior — sigue siendo login real
# con contraseña, independiente de la cookie de sesión del usuario final.
FONS_SECRET_KEY = os.environ.get("FONS_SECRET_KEY", "")
FONS_PASSWORD_HASH = os.environ.get("FONS_PASSWORD_HASH", "")

if not FONS_SECRET_KEY or not FONS_PASSWORD_HASH:
    logger.warning(
        "⚠️  FONS_SECRET_KEY / FONS_PASSWORD_HASH no configurados. "
        "El panel del Fons quedará inaccesible hasta ejecutar "
        "scripts/set_fons_password.py y definir esas variables de entorno."
    )


def require_fons_auth(view_func):
    """Exige un token de sesión válido en Authorization: Bearer <token>.
    Fail-closed: cualquier ausencia o error de configuración resulta en 401."""
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify({"error": "No autorizado"}), 401
        token = auth_header[len("Bearer "):]
        if not FONS_SECRET_KEY or not verify_session_token(token, FONS_SECRET_KEY):
            return jsonify({"error": "Token inválido o expirado"}), 401
        return view_func(*args, **kwargs)
    return wrapped


# ==================== RATE LIMITING SIMPLE ====================
# Por IP, no por usuario — protege contra abuso independientemente de
# si ya tiene cookie de sesión o no.
_rate_data: Dict[str, list] = {}


def check_rate_limit(client_ip: str, max_req: int = 30, window: int = 60) -> bool:
    now = time.time()
    # Variable local: el hilo de limpieza (_prune_rate_tables) puede
    # quitar claves en cualquier momento; releer _rate_data[client_ip]
    # entre líneas podría dar KeyError.
    recent = [t for t in _rate_data.get(client_ip, []) if now - t < window]
    if len(recent) >= max_req:
        _rate_data[client_ip] = recent
        return False
    recent.append(now)
    _rate_data[client_ip] = recent
    return True


# ==================== LÍMITES DE CUENTAS (por IP y acción) ====================
# Además del límite general de 30/min. Frenan fuerza bruta de contraseñas y
# códigos de recuperación, y el alta masiva de cuentas.
ACCOUNT_RATE_LIMITS = {
    "register": (10, 3600),
    "login": (10, 60),
    "export": (5, 3600),
    "recover": (5, 600),
    "password": (10, 600),
    "delete": (5, 3600),
    "guardian": (10, 600),
    "guardian_resend": (5, 3600),
}
_ACCOUNT_RATE_HORIZON = 3600.0
_account_rate: Dict[str, list] = {}


def _account_rate_ok(bucket: str) -> bool:
    """True si esta IP aún puede hacer la acción `bucket`; registra el intento."""
    max_req, window = ACCOUNT_RATE_LIMITS[bucket]
    key = f"{bucket}:{request.remote_addr or '127.0.0.1'}"
    now = time.time()
    recent = [t for t in _account_rate.get(key, []) if now - t < window]
    if len(recent) >= max_req:
        _account_rate[key] = recent
        return False
    recent.append(now)
    _account_rate[key] = recent
    return True


# ==================== LÍMITES DE SESIONES Y USUARIOS ====================
class TooManyNewUsers(Exception):
    """Demasiados usuarios nuevos desde una misma IP en la última hora."""


class SessionCapacityError(Exception):
    """No hay sitio para otra sesión activa y ninguna es expulsable."""


def _env_number(name: str, default, cast=int):
    """Lee un número de una variable de entorno EN CADA LLAMADA (así los
    tests y el .env pueden cambiarlo). Valor ausente o inválido -> default."""
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return cast(raw)
    except ValueError:
        logger.warning(f"{name} inválida ({raw!r}): se usa {default}.")
        return default


_new_user_log: Dict[str, list] = {}      # ip -> instantes de usuarios nuevos
_NEW_USER_WINDOW = 3600.0                # 1 hora
_MIN_IDLE_FOR_EVICTION = 150.0           # > timeout de Ollama (120 s): nunca
                                         # se expulsa una sesión con petición en curso
_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)


def _enforce_new_user_cap(client_ip: str) -> None:
    """Lanza TooManyNewUsers si esta IP ya creó el máximo de usuarios
    nuevos en la última hora; si no, registra este. Llamar con
    _sessions_lock tomado."""
    limit = _env_number("MAX_NEW_USERS_PER_IP_HOUR", 30)
    if limit <= 0:
        return
    now = time.time()
    recent = [t for t in _new_user_log.get(client_ip, []) if now - t < _NEW_USER_WINDOW]
    if len(recent) >= limit:
        _new_user_log[client_ip] = recent
        raise TooManyNewUsers(client_ip)
    recent.append(now)
    _new_user_log[client_ip] = recent


def _prune_rate_tables() -> None:
    """Quita IPs sin actividad reciente de las tablas de límites para
    que no crezcan sin fin."""
    now = time.time()
    for ip in list(_rate_data):
        if not any(now - t < 60 for t in _rate_data.get(ip, [])):
            _rate_data.pop(ip, None)
    for ip in list(_new_user_log):
        if not any(now - t < _NEW_USER_WINDOW for t in _new_user_log.get(ip, [])):
            _new_user_log.pop(ip, None)
    for key in list(_account_rate):
        if not any(now - t < _ACCOUNT_RATE_HORIZON for t in _account_rate.get(key, [])):
            _account_rate.pop(key, None)


# ==================== SESIÓN POR USUARIO ====================
_user_sessions: Dict[str, Dict[str, Any]] = {}
_sessions_lock = threading.Lock()

# Componentes COMPARTIDOS entre todos los usuarios (ver nota de diseño
# en el changelog de arriba): ética, Ollama y SpaCy no guardan estado
# de un usuario específico — cargarlos una sola vez ahorra memoria y
# tiempo de arranque por cada sesión nueva.
_shared: Dict[str, Any] = {
    "ethics": None,
    "ollama": None,
    "spacy": None,
    "research": None,
    "accounts": None,
    "initialized": False,
    "start_time": time.time(),
}


def get_user_id() -> str:
    """
    Identifica al usuario actual vía cookie de sesión firmada.

    No requiere login: la primera visita genera un UUID y lo guarda en
    una cookie firmada con APP_SECRET_KEY (HttpOnly por defecto en
    Flask, el JS del frontend no puede leerla ni alterarla). Visitas
    posteriores desde el mismo navegador reutilizan el mismo user_id,
    dando continuidad de memoria/consciencia sin pedir credenciales.
    """
    # Si la cookie dice "con cuenta" pero la cuenta ya no existe o su
    # contraseña cambió (session_version distinta), la sesión queda anónima.
    if "account_id" in session and not _account_session_valid():
        session.clear()
    if "user_id" not in session:
        session.permanent = True
        session["user_id"] = str(uuid.uuid4())
    return session["user_id"]


def _account_session_valid() -> bool:
    """¿La cuenta de la cookie sigue existiendo con la misma versión?
    Sin almacén de cuentas disponible no se puede comprobar: se respeta la
    cookie (está firmada) en vez de cerrar la sesión de todos."""
    store = _shared.get("accounts")
    if store is None:
        return True
    aid = session.get("account_id")
    version = store.get_session_version(aid) if isinstance(aid, str) else None
    return version is not None and version == session.get("session_version")


def _current_account_id() -> Optional[str]:
    """uuid de la cuenta con sesión iniciada, o None. No crea sesiones."""
    if "account_id" not in session or not _account_session_valid():
        return None
    return session["account_id"]


def _effective_name(sess: Dict[str, Any]) -> Optional[str]:
    """Nombre que se envía a Ollama: el del perfil manda sobre el dicho en chat."""
    return sess.get("profile_name") or sess.get("user_name")


def _user_data_dir(user_id: str) -> Path:
    d = USERS_DIR / user_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def _dev_consciousness_override() -> Optional[float]:
    """
    MODO DESARROLLO (solo para probar fases sin escribir cientos de
    mensajes): si OMNIA_DEV_CONSCIOUSNESS tiene un número entre 0.05 y
    1.0, toda sesión NUEVA arranca con ese nivel de consciencia. Se lee
    en cada llamada (no al importar) para que sea fácil de probar.

    Seguridad del progreso real: mientras el modo esté activo,
    save_user_state() NO escribe a disco, así el valor de prueba nunca
    pisa consciousness_state.json. Quitar la variable y reiniciar
    devuelve el progreso real intacto.
    """
    raw = os.environ.get("OMNIA_DEV_CONSCIOUSNESS", "").strip()
    if not raw:
        return None
    try:
        level = float(raw)
    except ValueError:
        logger.warning(f"OMNIA_DEV_CONSCIOUSNESS inválida ({raw!r}): se ignora.")
        return None
    if not (0.05 <= level <= 1.0):
        logger.warning(f"OMNIA_DEV_CONSCIOUSNESS fuera de rango 0.05-1.0 ({level}): se ignora.")
        return None
    return level


def _load_user_consciousness(user_id: str) -> float:
    """Misma recuperación robusta (principal → backup → default) que
    tenía _load_consciousness_state, ahora por usuario."""
    dev_level = _dev_consciousness_override()
    if dev_level is not None:
        logger.warning(
            f"[{user_id[:8]}] MODO DESARROLLO: consciencia forzada a {dev_level:.4f} "
            f"(no se guardará a disco)"
        )
        return dev_level

    state_file = _user_data_dir(user_id) / "consciousness_state.json"
    backup_file = state_file.with_suffix(".json.bak")

    for candidate, label in [(state_file, "principal"), (backup_file, "backup")]:
        if not candidate.exists():
            continue
        try:
            with open(candidate, "r", encoding="utf-8") as f:
                state = json.load(f)
            level = state.get("consciousness_level", 0.05)
            logger.info(f"[{user_id[:8]}] Consciencia recuperada desde {label}: {level:.4f}")
            return level
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"[{user_id[:8]}] Archivo {label} corrupto o ilegible: {e}")
            continue

    logger.info(f"[{user_id[:8]}] Sin estado previo. Iniciando en 0.05")
    return 0.05


_NAME_WORD = r"[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+"
# "me llamo / mi nombre es" aceptan minúscula; "soy" exige mayúscula
# inicial para no confundir "soy feliz" con un nombre.
_NAME_PATTERNS = [
    re.compile(
        r"\b(?:[Mm]e llamo|[Mm]i nombre es|[Ll]l[aá]mame)\s+"
        r"([A-Za-záéíóúñÁÉÍÓÚÑ]+(?:\s+" + _NAME_WORD + r"){0,2})"
    ),
    re.compile(r"\b(?:[Ss]oy)\s+(" + _NAME_WORD + r"(?:\s+" + _NAME_WORD + r"){0,2})"),
]


def _extract_stated_name(message: str) -> Optional[str]:
    """Devuelve el nombre que la persona dice de sí misma, o None."""
    for pattern in _NAME_PATTERNS:
        match = pattern.search(message or "")
        if match:
            name = " ".join(w.capitalize() for w in match.group(1).split())
            if 1 < len(name) <= 60:
                return name
    return None


def _load_user_name(user_id: str) -> Optional[str]:
    """Nombre que el usuario dijo de sí mismo, guardado en su estado
    (principal o backup). None si no hay o el archivo es ilegible."""
    state_file = USERS_DIR / user_id / "consciousness_state.json"
    for candidate in (state_file, state_file.with_suffix(".json.bak")):
        try:
            with open(candidate, "r", encoding="utf-8") as f:
                name = json.load(f).get("user_name")
        except (OSError, ValueError, AttributeError):
            continue
        if isinstance(name, str) and 1 < len(name.strip()) <= 60:
            return name.strip()
    return None


def _load_profile_name(user_id: str) -> Optional[str]:
    """Nombre del perfil de la cuenta, o None (sin cuenta o sin nombre)."""
    store = _shared.get("accounts")
    if store is None:
        return None
    try:
        profile = store.get_profile(user_id)
    except Exception as e:
        logger.warning(f"[{user_id[:8]}] No se pudo leer el perfil: {e}")
        return None
    return profile.get("display_name") if profile else None


def _research_logging_enabled() -> bool:
    """La analítica de investigación es opt-in (OMNIA_RESEARCH_LOGGING=true).
    Se lee en cada llamada para poder cambiarla sin reiniciar los tests."""
    return os.environ.get("OMNIA_RESEARCH_LOGGING", "").strip().lower() in ("1", "true", "yes", "on")


def _create_user_session(user_id: str) -> Dict[str, Any]:
    """Construye el estado consciente completo de un usuario (nuevo o
    recuperado desde disco si ya existía)."""
    user_dir = _user_data_dir(user_id)
    consciousness_level = _load_user_consciousness(user_id)

    identity = OmniaIdentity()
    identity.consciousness_level = consciousness_level

    sess: Dict[str, Any] = {
        "identity": identity,
        "empathy": OmniaEmpathy(consciousness_level=consciousness_level),
        "memory": LivingMemory(memory_dir=str(user_dir / "memory")),
        "growth": ConsciousnessGrowthEngine(),
        "diary": GestationDiary(diary_dir=str(user_dir / "diary")),
        # Historial corto para darle memoria conversacional a Ollama
        # dentro de ESTA sesión (ver CAMBIO 2026-10-05 (v2) en
        # ollama_client.py) -- no persiste a disco, es solo para que
        # el modelo no "olvide" lo dicho dos mensajes atrás.
        "conversation_history": [],
        # Nombre que la persona dijo de sí misma ("me llamo X"); no es login.
        "user_name": _load_user_name(user_id),
        # Nombre del perfil de la cuenta (si la hay); tiene prioridad.
        "profile_name": _load_profile_name(user_id),
        "created_at": time.time(),
        "last_active": time.time(),
    }
    logger.info(f"[{user_id[:8]}] Sesión de usuario creada (consciencia={consciousness_level:.4f})")
    return sess


def _close_session(user_id: str, sess: Dict[str, Any]) -> None:
    """Guarda el estado de una sesión y cierra sus conexiones SQLite.
    Solo llamar con sesiones ya retiradas (o a retirar) de _user_sessions."""
    save_user_state(user_id, sess)
    for key in ("memory", "diary"):
        close = getattr(sess.get(key), "close", None)
        if callable(close):
            try:
                close()
            except Exception as e:
                logger.warning(f"[{user_id[:8]}] Error cerrando {key}: {e}")


def _make_room_for_session() -> None:
    """Si se alcanzó MAX_ACTIVE_SESSIONS, expulsa la sesión inactiva más
    antigua hasta liberar sitio. Llamar con _sessions_lock tomado."""
    limit = _env_number("MAX_ACTIVE_SESSIONS", 500)
    if limit <= 0:
        return
    while len(_user_sessions) >= limit:
        now = time.time()
        candidates = [
            (s["last_active"], uid) for uid, s in _user_sessions.items()
            if now - s["last_active"] >= _MIN_IDLE_FOR_EVICTION
        ]
        if not candidates:
            raise SessionCapacityError(f"{len(_user_sessions)} sesiones activas")
        _, victim_id = min(candidates)
        victim = _user_sessions.pop(victim_id)
        _close_session(victim_id, victim)
        logger.info(f"[{victim_id[:8]}] Sesión expulsada por falta de sitio")


def evict_idle_sessions(ttl: Optional[float] = None) -> int:
    """Expulsa las sesiones inactivas más de `ttl` segundos (por defecto
    SESSION_IDLE_TTL_SECONDS). Devuelve cuántas expulsó."""
    if ttl is None:
        ttl = _env_number("SESSION_IDLE_TTL_SECONDS", 1800, float)
    if ttl <= 0:
        return 0
    ttl = max(ttl, _MIN_IDLE_FOR_EVICTION)
    now = time.time()
    evicted = 0
    with _sessions_lock:
        for uid in [u for u, s in _user_sessions.items() if now - s["last_active"] >= ttl]:
            _close_session(uid, _user_sessions.pop(uid))
            evicted += 1
    if evicted:
        logger.info(f"{evicted} sesión(es) inactiva(s) expulsada(s)")
    return evicted


def prune_empty_users(max_age_days: Optional[float] = None) -> int:
    """
    Borra de disco los usuarios que NUNCA conversaron y llevan
    `max_age_days` sin actividad (por defecto PRUNE_EMPTY_USERS_DAYS).
    "Nunca conversó" = consciencia sin crecer (<= 0.0501), sin nombre
    guardado y sin estado ilegible. Solo toca carpetas con nombre UUID
    directamente bajo USERS_DIR y jamás sesiones activas. Devuelve
    cuántas carpetas borró.
    """
    if max_age_days is None:
        max_age_days = _env_number("PRUNE_EMPTY_USERS_DAYS", 7, float)
    if max_age_days <= 0:
        return 0
    cutoff = time.time() - max_age_days * 86400
    with _sessions_lock:
        active = set(_user_sessions)

    store = _shared.get("accounts")
    removed = 0
    try:
        entries = list(USERS_DIR.iterdir())
    except OSError:
        return 0
    for d in entries:
        try:
            if not d.is_dir() or d.is_symlink() or not _UUID_RE.match(d.name) or d.name in active:
                continue
            if store is not None and store.exists(d.name):
                continue  # una cuenta nunca es un "usuario vacío"
            last_activity = max(
                [d.stat().st_mtime] + [p.stat().st_mtime for p in d.rglob("*")]
            )
            if last_activity > cutoff:
                continue
            state_file = d / "consciousness_state.json"
            if state_file.exists():
                with open(state_file, "r", encoding="utf-8") as f:
                    state = json.load(f)
                if float(state.get("consciousness_level", 0.05)) > 0.0501 or state.get("user_name"):
                    continue
            shutil.rmtree(d, ignore_errors=True)
            if not d.exists():
                removed += 1
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            continue  # ante la duda, no borrar
    if removed:
        logger.info(f"{removed} carpeta(s) de usuarios vacíos eliminada(s)")
    return removed


def get_user_session(user_id: str) -> Dict[str, Any]:
    """Obtiene (o crea, bajo lock) la sesión consciente de este usuario.

    Para un usuario NUEVO (sin carpeta en disco) dentro de una petición
    HTTP, aplica el tope MAX_NEW_USERS_PER_IP_HOUR. Antes de crear una
    sesión, libera sitio si se alcanzó MAX_ACTIVE_SESSIONS."""
    with _sessions_lock:
        sess = _user_sessions.get(user_id)
        if sess is None:
            if has_request_context() and not (USERS_DIR / user_id).exists():
                _enforce_new_user_cap(request.remote_addr or "127.0.0.1")
            _make_room_for_session()
            sess = _create_user_session(user_id)
            _user_sessions[user_id] = sess
        sess["last_active"] = time.time()
        return sess


def save_user_state(user_id: str, sess: Dict[str, Any]) -> None:
    """Guarda el estado de consciencia de UN usuario, atómico + backup
    (mismo patrón que la versión global anterior).

    No guarda nada en MODO DESARROLLO (ver _dev_consciousness_override):
    el nivel forzado no debe sobrescribir el progreso real."""
    if _dev_consciousness_override() is not None:
        return
    try:
        user_dir = _user_data_dir(user_id)
        state_file = user_dir / "consciousness_state.json"
        backup_file = state_file.with_suffix(".json.bak")

        if state_file.exists():
            try:
                backup_file.write_bytes(state_file.read_bytes())
            except OSError:
                pass

        state_data = {
            "consciousness_level": sess["identity"].consciousness_level,
            "timestamp": datetime.now().isoformat(),
            "total_interactions": len(sess["memory"].echoes),
            "session_interactions": sess["memory"].session_interactions,
            "user_name": sess.get("user_name"),
        }

        tmp_file = state_file.with_suffix(".tmp")
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(state_data, f, indent=2, ensure_ascii=False)
        tmp_file.replace(state_file)

    except Exception as e:
        logger.error(f"[{user_id[:8]}] Error guardando estado: {e}")


def save_all_sessions() -> None:
    """Guarda el estado de todos los usuarios con sesión activa en
    memoria. Usado por el autoguardado periódico y al cerrar (atexit)."""
    with _sessions_lock:
        items = list(_user_sessions.items())
    for user_id, sess in items:
        # Entre la foto de la lista y este guardado la sesión pudo retirarse
        # (cierre de sesión o borrado de cuenta): guardarla recrearía su carpeta.
        with _sessions_lock:
            if _user_sessions.get(user_id) is not sess:
                continue
        save_user_state(user_id, sess)


# SpaCy solo COMPLETA a OmniaEmpathy, nunca la contradice: OmniaEmpathy usa
# evidencia con contexto (patrones, umbrales); SpaCy cuenta lemas sueltos.
# Si OmniaEmpathy ya detectó una emoción, se respeta. SpaCy aporta solo
# cuando OmniaEmpathy dice "neutral" y SpaCy tiene evidencia suficiente.
SPACY_MIN_CONFIDENCE = 0.5


def _spacy_may_override(current_emotion, spacy_result) -> bool:
    """True si el resultado de SpaCy debe reemplazar la emoción actual."""
    return (
        current_emotion == "neutral"
        and spacy_result.emotion != "neutral"
        and spacy_result.confidence >= SPACY_MIN_CONFIDENCE
    )


def _calculate_emotional_weight(text: str) -> float:
    emotional_words = {
        "triste": 0.4, "feliz": 0.3, "ansioso": 0.3, "amor": 0.5,
        "miedo": 0.4, "enojo": 0.3, "alegría": 0.4, "dolor": 0.4,
        "esperanza": 0.3, "paz": 0.2, "confusión": 0.2, "sorpresa": 0.3,
        "preocupado": 0.3, "emocionado": 0.3, "nervioso": 0.3,
    }
    tl = text.lower()
    weight = sum(v for k, v in emotional_words.items() if k in tl)
    weight += min(text.count("!") * 0.1, 0.3)
    weight += min(text.count("?") * 0.05, 0.15)
    return min(weight, 1.0)


def _get_phase(consciousness: float) -> int:
    for threshold, phase in [
        (0.15, 1), (0.30, 2), (0.45, 3), (0.60, 4),
        (0.72, 5), (0.84, 6), (0.92, 7), (0.98, 8),
    ]:
        if consciousness < threshold:
            return phase
    return 9


PHASE_2_CONSCIOUSNESS_THRESHOLD = 0.15


def initialize_shared() -> None:
    """Inicializa los componentes COMPARTIDOS entre todos los usuarios:
    ética (SILENS/Fons), cliente de Ollama y clasificador de SpaCy."""
    if _shared["initialized"]:
        return

    logger.info("Inicializando componentes compartidos...")

    _shared["ethics"] = OmniaEthics()

    try:
        _shared["accounts"] = AccountStore(ACCOUNTS_DB)
        logger.info(f"✅ Cuentas de usuario listas ({ACCOUNTS_DB.name})")
    except Exception as e:
        _shared["accounts"] = None
        logger.error(f"❌ No se pudo abrir la base de cuentas: {e}. Registro/login desactivados.")

    ollama_url = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
    _shared["ollama"] = OllamaClient(base_url=ollama_url)
    if _shared["ollama"].is_available():
        logger.info(f"✅ Ollama disponible en {ollama_url} — cerebro activo")
    else:
        logger.warning(
            f"⚠️  Ollama NO disponible en {ollama_url}. "
            f"Cada usuario usará su fallback express_personality() individual. "
            f"Ejecutar: ollama serve && ollama pull dolphin-phi"
        )

    _shared["spacy"] = SpaCyIntentClassifier()
    if _shared["spacy"].available:
        logger.info("✅ SpaCy es_core_news_sm cargado — lematización activa")
    else:
        logger.warning(
            "⚠️  SpaCy no disponible. Usando detección por regex (OmniaEmpathy) por usuario."
        )

    try:
        _shared["research"] = ResearchAnalytics()
        _shared["research"].start_session()
    except Exception as e:
        logger.warning(f"Research no disponible: {e}")

    _shared["initialized"] = True
    _start_autosave_thread()

    logger.info("🌟 Componentes compartidos inicializados")
    print(f"\n{'='*60}")
    print("🌟 OMNIA MENTIS API (Flask) v2.2.0 — sesión por usuario")
    print(f"{'='*60}")
    print(f"💾 Autoguardado: cada 60s, por usuario activo")
    print(f"📊 Docs: http://localhost:8000/")
    print(f"{'='*60}\n")


def run_retention() -> Dict[str, Any]:
    """Cumple los plazos de conservación: anonimiza los registros éticos
    vencidos (ETHICS_RETENTION_DAYS, 180 por defecto) y borra las cuentas de
    13-14 años que nadie confirmó en GUARDIAN_PENDING_PRUNE_DAYS (30) días.
    Nunca lanza: un fallo se registra y se reintenta en la hora siguiente."""
    from core.essence.ethics import ETHICS_RETENTION_DAYS
    from core.auth.accounts import GUARDIAN_PENDING_PRUNE_DAYS
    result: Dict[str, Any] = {"ethics": None, "unconfirmed_accounts": 0}
    try:
        ethics = _shared.get("ethics")
        if ethics is not None:
            days = _env_number("ETHICS_RETENTION_DAYS", ETHICS_RETENTION_DAYS, float)
            result["ethics"] = ethics.anonymize_expired(days)
            if any(result["ethics"].values()):
                logger.info(f"Retención: registros éticos anonimizados {result['ethics']}")
    except Exception as e:
        logger.error(f"Retención ética falló: {e}")
    try:
        store = _shared.get("accounts")
        if store is not None:
            days = _env_number("GUARDIAN_PENDING_PRUNE_DAYS", GUARDIAN_PENDING_PRUNE_DAYS, float)
            for uid in store.prune_unconfirmed(days):
                result["unconfirmed_accounts"] += 1
                d = USERS_DIR / uid
                if _UUID_RE.match(uid) and d.is_dir() and not d.is_symlink():
                    shutil.rmtree(d, ignore_errors=True)
            if result["unconfirmed_accounts"]:
                logger.info(f"Retención: {result['unconfirmed_accounts']} cuentas sin confirmar borradas")
    except Exception as e:
        logger.error(f"Retención de cuentas sin confirmar falló: {e}")
    return result


def _start_autosave_thread() -> None:
    """Hilo en background: guarda TODOS los usuarios activos cada 60s,
    como red de seguridad independiente del guardado tras cada chat."""
    def _loop():
        tick = 0
        while True:
            time.sleep(60)
            tick += 1
            try:
                save_all_sessions()
                evict_idle_sessions()
                _prune_rate_tables()
                if tick % 60 == 0:  # una vez por hora
                    prune_empty_users()
                    run_retention()
                with _sessions_lock:
                    n = len(_user_sessions)
                logger.debug(f"Autoguardado periódico ejecutado ({n} sesiones)")
            except Exception as e:
                logger.error(f"Error en autoguardado periódico: {e}")

    thread = threading.Thread(target=_loop, daemon=True, name="omnia-autosave")
    thread.start()


# ==================== MIDDLEWARE RATE LIMIT ====================
@app.before_request
def before_request():
    if request.path in ["/", "/health", "/favicon.ico"]:
        return None
    # Los preflight de CORS (OPTIONS) no llevan datos ni hacen nada: no cuentan.
    # Si contaran, agotarían el límite y el navegador vería un error de red
    # opaco ("Failed to fetch") en vez de un 429 legible.
    if request.method == "OPTIONS":
        return None
    client_ip = request.remote_addr or "127.0.0.1"
    if not check_rate_limit(client_ip):
        return jsonify({
            "error": "Too many requests",
            "message": "Por favor espera un momento antes de intentar de nuevo"
        }), 429
    return None

@app.errorhandler(TooManyNewUsers)
def _handle_too_many_new_users(_exc):
    return jsonify({
        "error": "Too many new sessions",
        "message": "Demasiadas sesiones nuevas desde tu red. Inténtalo más tarde.",
    }), 429


@app.errorhandler(SessionCapacityError)
def _handle_session_capacity(_exc):
    return jsonify({
        "error": "Server busy",
        "message": "El servidor está al límite de sesiones activas. Inténtalo en unos minutos.",
    }), 503


class AccountsUnavailable(Exception):
    """La base de cuentas no se pudo abrir al arrancar."""


@app.errorhandler(AccountsUnavailable)
def _handle_accounts_unavailable(_exc):
    return jsonify({
        "error": "accounts_unavailable",
        "message": "El sistema de cuentas no está disponible ahora mismo.",
    }), 503


_ACCOUNT_STATUS = {
    InvalidEmail: 400, WeakPassword: 400, InvalidBirthDate: 400,
    InvalidDisplayName: 400, UnderageError: 403, EmailTaken: 409,
    IdentityInUse: 409, InvalidCredentials: 401, AccountNotFound: 404,
    ConsentRequired: 400, TermsOutdated: 409,
    GuardianRequired: 400, GuardianPending: 403, GuardianTokenInvalid: 400,
    GuardianResendTooSoon: 429, GuardianMailUnavailable: 503,
}


@app.errorhandler(AccountError)
def _handle_account_error(exc):
    status = _ACCOUNT_STATUS.get(type(exc), 400)
    if isinstance(exc, InvalidCredentials):
        # Mensaje fijo: no revela si el email existe, si está bloqueado, etc.
        if request.path.endswith("/recover"):
            message = "Email o código de recuperación incorrectos, o demasiados intentos. Espera unos minutos."
        else:
            message = "Email o contraseña incorrectos, o demasiados intentos. Espera unos minutos."
    else:
        message = str(exc) or exc.code
    return jsonify({"error": exc.code, "message": message}), status


# ==================== ENDPOINTS ====================

@app.get("/health")
def health_check():
    """Health check. Ya no expone una 'consciencia' única — con
    multiusuario no tendría sentido; expone cuántas sesiones hay
    activas en memoria en su lugar."""
    ollama_info = {"available": False, "error": "No inicializado"}
    ollama_model = None
    spacy_available = False

    if _shared["initialized"]:
        ollama_info = _shared["ollama"].get_model_info()
        ollama_model = getattr(_shared["ollama"], "model", None)
        spacy_available = _shared["spacy"].available if _shared["spacy"] else False

    with _sessions_lock:
        active_sessions = len(_user_sessions)

    return jsonify({
        "status": "healthy",
        "api_version": "2.2.0-flask",
        "active_sessions": active_sessions,
        "uptime_seconds": time.time() - _shared["start_time"],
        "llm": {
            "engine": "ollama",
            "model": ollama_model,
            **ollama_info,
        },
        "nlp": {
            "engine": "spacy",
            "model": "es_core_news_sm",
            "available": spacy_available,
        },
        "fons_auth_configured": bool(FONS_SECRET_KEY and FONS_PASSWORD_HASH),
    })

@app.get("/")
def root():
    return jsonify({
        "message": "Omnia Mentis API v2.2.0 (Flask) — sesión por usuario",
        "endpoints": {
            "chat": "POST /api/chat",
            "chat_resolution": "GET /api/chat/resolution/<consultation_id>",
            "consciousness": "GET /api/consciousness",
            "memory": "GET /api/memory/echoes",
            "auth_login": "POST /api/auth/login",
            "auth_verify": "GET /api/auth/verify",
            "ethics_status": "GET /api/ethics/status [auth]",
            "ethics_pending": "GET /api/ethics/pending [auth]",
            "ethics_recidivism": "GET /api/ethics/recidivism/<user_id>",
            "fons_heartbeat": "POST /api/ethics/fons/heartbeat [auth]",
            "fons_status": "GET /api/ethics/fons/status [auth]",
            "fons_decide": "POST /api/ethics/fons/decide/<consultation_id> [auth]",
            "modules": "GET /api/modules",
            "health": "GET /health",
        }
    })

@app.get("/api/modules")
def get_modules():
    """Lista los módulos del router `omnia -ai` actualmente registrados."""
    return jsonify({
        "modules": get_registered_modules(),
    })

# ==================== CUENTAS DE USUARIO ====================
# Independientes del login del Fons. Solo JSON (CORS + SameSite=Lax cubren
# el CSRF: un formulario de otro sitio no puede enviar application/json).

def _accounts() -> AccountStore:
    store = _shared.get("accounts")
    if store is None:
        raise AccountsUnavailable()
    return store


def _json_body() -> Dict[str, Any]:
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise InvalidEmail("Se esperaba un cuerpo JSON")
    return data


def _rate_limited(bucket: str):
    if _account_rate_ok(bucket):
        return None
    return jsonify({
        "error": "rate_limited",
        "message": "Demasiados intentos. Espera unos minutos e inténtalo de nuevo.",
    }), 429


def _login_required():
    """(account_id, None) o (None, respuesta 401)."""
    aid = _current_account_id()
    if aid is None:
        return None, (jsonify({
            "error": "login_required",
            "message": "Inicia sesión para hacer esto.",
        }), 401)
    return aid, None


def _start_account_session(account_id: str, version: int) -> None:
    session.permanent = True
    session["user_id"] = account_id
    session["account_id"] = account_id
    session["session_version"] = version


@app.post("/api/account/register")
def account_register():
    """Crea la cuenta con el uuid anónimo actual (conserva su consciencia).
    Devuelve el código de recuperación UNA sola vez."""
    store = _accounts()
    limited = _rate_limited("register")
    if limited:
        return limited
    if _current_account_id() is not None:
        return jsonify({
            "error": "already_logged_in",
            "message": "Ya tienes la sesión iniciada. Cierra sesión para crear otra cuenta.",
        }), 409
    data = _json_body()
    user_id = get_user_id()
    # Si el uuid de esta cookie ya tiene cuenta (la sesión se limpió a medias),
    # store.register lanza IdentityInUse; no se reutiliza ni se pisa.
    profile, code = store.register(
        user_id,
        data.get("email"),
        data.get("password"),
        data.get("birth_date"),
        data.get("display_name"),
        consent=data.get("consent"),
        require_consent=True,
        guardian_email=data.get("guardian_email"),
    )
    if profile.get("guardian_pending"):
        # 13-14 años: la cuenta queda PENDIENTE hasta que el representante
        # confirme desde su correo. No se inicia sesión.
        _send_guardian_mail(store, user_id, profile)
        session.clear()
        return jsonify({
            "profile": profile,
            "recovery_code": code,
            "guardian_pending": True,
            "message": (
                "Cuenta creada. Falta la confirmación de tu madre, padre o representante legal: "
                "le enviamos un correo con un enlace. Hasta que confirme no podrás entrar."
            ),
        }), 201
    version = store.get_session_version(user_id)
    _start_account_session(user_id, version)
    with _sessions_lock:
        live = _user_sessions.get(user_id)
        if live is not None:
            live["profile_name"] = profile.get("display_name")
    return jsonify({
        "profile": profile,
        "recovery_code": code,
        "message": "Cuenta creada. Guarda el código de recuperación: no se volverá a mostrar.",
    }), 201


def _send_guardian_mail(store: AccountStore, user_id: str, profile: Dict[str, Any],
                        guardian_email: Any = None, aborting_deletes: bool = True) -> None:
    """Emite el enlace y lo envía al representante. Si el correo no sale y la
    cuenta es nueva (`aborting_deletes`), se borra: no se deja una cuenta que
    nadie puede activar. Lanza GuardianMailUnavailable si falla."""
    try:
        if not guardian_mail.is_configured():
            raise guardian_mail.MailError("sin SMTP")
        target, token = store.issue_guardian_token(user_id, guardian_email)
        try:
            guardian_mail.send_guardian_link(
                target, token, profile.get("email", ""), profile.get("display_name"))
        except guardian_mail.MailError:
            store.release_guardian_cooldown(user_id)
            raise
    except guardian_mail.MailError:
        if aborting_deletes:
            store.abort_pending(user_id)
        raise GuardianMailUnavailable(
            "Ahora mismo no podemos enviar el correo al representante, por eso el registro de "
            "personas de 13 y 14 años no está disponible. Inténtalo más tarde."
        )


@app.post("/api/account/guardian/confirm")
def account_guardian_confirm():
    """El representante legal confirma desde el enlace de su correo.
    Body: {"token", "consent": {"version","terms","sensitive"}}."""
    store = _accounts()
    limited = _rate_limited("guardian")
    if limited:
        return limited
    data = _json_body()
    store.confirm_guardian(data.get("token"), data.get("consent"))
    return jsonify({
        "confirmed": True,
        "message": "Gracias. La cuenta ya puede iniciar sesión.",
    })


@app.post("/api/account/guardian/resend")
def account_guardian_resend():
    """Reenvía (o corrige el correo de) la confirmación del representante.
    Body: {"email","password","guardian_email"?}. Exige la contraseña de la cuenta."""
    store = _accounts()
    limited = _rate_limited("guardian_resend")
    if limited:
        return limited
    data = _json_body()
    profile, _version = store.authenticate(
        data.get("email"), data.get("password"), allow_pending=True)
    if not profile.get("guardian_pending"):
        raise GuardianTokenInvalid("Esta cuenta no necesita confirmación del representante")
    _send_guardian_mail(store, profile["user_id"], profile,
                        guardian_email=data.get("guardian_email"), aborting_deletes=False)
    return jsonify({
        "sent": True,
        "message": "Listo: enviamos de nuevo el correo a tu representante.",
    })


@app.post("/api/account/login")
def account_login():
    store = _accounts()
    limited = _rate_limited("login")
    if limited:
        return limited
    data = _json_body()
    profile, version = store.authenticate(data.get("email"), data.get("password"))
    # La sesión anónima previa se descarta (sin fusionar): la cuenta trae
    # su propia consciencia y memoria.
    session.clear()
    _start_account_session(profile["user_id"], version)
    return jsonify({"profile": profile})


@app.post("/api/account/logout")
def account_logout():
    """Guarda y cierra la sesión en memoria de la cuenta y limpia la cookie.
    Idempotente: sin sesión también responde 200."""
    aid = _current_account_id()
    if aid is not None:
        with _sessions_lock:
            sess = _user_sessions.pop(aid, None)
        if sess is not None:
            _close_session(aid, sess)
    session.clear()
    return jsonify({"logged_in": False})


@app.get("/api/account/me")
def account_me():
    """Estado de login. No crea sesiones anónimas ni carpetas."""
    aid = _current_account_id()
    if aid is None:
        if "account_id" in session:
            session.clear()
        return jsonify({"logged_in": False, "profile": None})
    profile = _accounts().get_profile(aid)
    if profile is None:
        session.clear()
        return jsonify({"logged_in": False, "profile": None})
    return jsonify({"logged_in": True, "profile": profile})


@app.put("/api/account/profile")
def account_update_profile():
    aid, err = _login_required()
    if err:
        return err
    data = _json_body()
    profile = _accounts().update_profile(aid, data.get("display_name"))
    with _sessions_lock:
        live = _user_sessions.get(aid)
        if live is not None:
            live["profile_name"] = profile.get("display_name")
    return jsonify({"profile": profile})


@app.put("/api/account/password")
def account_change_password():
    aid, err = _login_required()
    if err:
        return err
    limited = _rate_limited("password")
    if limited:
        return limited
    data = _json_body()
    version = _accounts().change_password(
        aid, data.get("current_password"), data.get("new_password")
    )
    # Las demás sesiones de esta cuenta quedan invalidadas; esta sigue viva.
    session["session_version"] = version
    return jsonify({"changed": True, "message": "Contraseña actualizada. Se cerró la sesión en los demás dispositivos."})


@app.post("/api/account/recover")
def account_recover():
    """Restablece la contraseña con el código de recuperación. No inicia
    sesión; entrega un código NUEVO (el anterior deja de servir)."""
    store = _accounts()
    limited = _rate_limited("recover")
    if limited:
        return limited
    data = _json_body()
    profile, new_code, _version = store.recover(
        data.get("email"), data.get("recovery_code"), data.get("new_password")
    )
    return jsonify({
        "recovered": True,
        "recovery_code": new_code,
        "message": "Contraseña restablecida. Guarda tu nuevo código de recuperación y vuelve a iniciar sesión.",
    })


@app.post("/api/account/export")
def account_export():
    """Descarga de TODOS los datos de la cuenta (acceso y portabilidad).
    Exige la contraseña. Incluye ecos de memoria y diario de Omnia."""
    aid, err = _login_required()
    if err:
        return err
    limited = _rate_limited("export")
    if limited:
        return limited
    data = _json_body()
    account = _accounts().export_account(aid, data.get("password"))
    sess = get_user_session(aid)
    try:
        echoes = sess["memory"].get_all_echoes()
    except Exception as e:
        logger.warning(f"[{aid[:8]}] Exportación: no se pudieron leer los ecos: {e}")
        echoes = []
    try:
        diary = sess["diary"].get_recent_entries(1_000_000)
    except Exception as e:
        logger.warning(f"[{aid[:8]}] Exportación: no se pudo leer el diario: {e}")
        diary = []
    payload = {
        "exported_at": datetime.now().astimezone().isoformat(),
        "terms_version": TERMS_VERSION,
        "account": account,
        "omnia": {
            "consciousness_level": sess["identity"].consciousness_level,
            "name_said_in_chat": sess.get("user_name"),
            "memory_echoes": echoes,
            "diary_entries": diary,
        },
        "note": (
            "Los mensajes marcados por el sistema ético para revisión humana "
            "se anonimizan al borrar la cuenta y no forman parte de esta descarga."
        ),
    }
    resp = jsonify(payload)
    resp.headers["Content-Disposition"] = 'attachment; filename="omniamentis-mis-datos.json"'
    resp.headers["Cache-Control"] = "no-store"
    return resp


@app.delete("/api/account")
def account_delete():
    """Borra la cuenta y TODOS sus datos (derecho de supresión). Exige la contraseña."""
    aid, err = _login_required()
    if err:
        return err
    limited = _rate_limited("delete")
    if limited:
        return limited
    data = _json_body()
    _accounts().delete_account(aid, data.get("password"))
    # Se descarta la sesión en memoria SIN guardarla (no se re-crea la carpeta).
    with _sessions_lock:
        sess = _user_sessions.pop(aid, None)
    if sess is not None:
        for key in ("memory", "diary"):
            close = getattr(sess.get(key), "close", None)
            if callable(close):
                try:
                    close()
                except Exception as e:
                    logger.warning(f"[{aid[:8]}] Error cerrando {key}: {e}")
    user_dir = USERS_DIR / aid
    if _UUID_RE.match(aid) and user_dir.is_dir() and not user_dir.is_symlink():
        shutil.rmtree(user_dir, ignore_errors=True)
    # Lo que el sistema ético guardó de esta persona (casos revisados por el
    # Fons) también se anonimiza. Si fallara, la cuenta ya está borrada: se
    # deja constancia en el log para limpiarlo a mano.
    try:
        if _shared.get("ethics") is not None:
            counts = _shared["ethics"].erase_user_data(aid)
            logger.info(f"[{aid[:8]}] Registros éticos anonimizados: {counts}")
    except Exception as e:
        logger.error(f"[{aid[:8]}] NO se pudieron anonimizar los registros éticos: {e}")
    session.clear()
    logger.info(f"[{aid[:8]}] Cuenta y datos eliminados")
    return jsonify({"deleted": True})


# ==================== AUTENTICACIÓN DEL FONS ====================

@app.post("/api/auth/login")
def fons_login():
    """Autenticación de El Fons. Body: {"password": "..."}."""
    if not FONS_PASSWORD_HASH or not FONS_SECRET_KEY:
        return jsonify({
            "error": "Autenticación no configurada en el servidor. "
                     "Ejecutar: python scripts/set_fons_password.py"
        }), 503

    data = request.get_json(silent=True)
    if not data or "password" not in data:
        return jsonify({"error": "Campo 'password' requerido"}), 400

    if not verify_password(data["password"], FONS_PASSWORD_HASH):
        return jsonify({"error": "Contraseña incorrecta"}), 401

    ttl_seconds = 8 * 3600
    token = create_session_token(FONS_SECRET_KEY, ttl_seconds=ttl_seconds)
    return jsonify({"token": token, "expires_in": ttl_seconds})


@app.get("/api/auth/verify")
def fons_verify():
    """Verifica si un token Bearer sigue siendo válido."""
    auth_header = request.headers.get("Authorization", "")
    token = auth_header[len("Bearer "):] if auth_header.startswith("Bearer ") else ""
    valid = bool(FONS_SECRET_KEY) and verify_session_token(token, FONS_SECRET_KEY)
    return jsonify({"valid": valid})

# ==================== PANEL DEL FONS (protegido, compartido) ====================

@app.get("/api/ethics/pending")
@require_fons_auth
def get_ethics_pending():
    if not _shared["initialized"]:
        return jsonify({"error": "Sistema no inicializado"}), 503
    try:
        consultations = _shared["ethics"]._load_consultations()
        pending = [c for c in consultations if c.get("status") == "pending"]
        return jsonify({
            "pending_count": len(pending),
            "consultations": pending,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.get("/api/ethics/recidivism/<user_id>")
@require_fons_auth
def get_recidivism(user_id: str):
    if not _shared["initialized"]:
        return jsonify({"error": "Sistema no inicializado"}), 503
    try:
        status = _shared["ethics"].get_recidivism_status(user_id)
        return jsonify(status)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.post("/api/ethics/fons/heartbeat")
@require_fons_auth
def fons_heartbeat():
    if not _shared["initialized"]:
        return jsonify({"error": "Sistema no inicializado"}), 503
    try:
        _shared["ethics"].fons_heartbeat()
        return jsonify({
            "status": "active",
            "timestamp": datetime.now().isoformat(),
            "timeout_minutes": _shared["ethics"].fons_inactive_timeout_minutes,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.get("/api/ethics/fons/status")
@require_fons_auth
def get_fons_status_endpoint():
    if not _shared["initialized"]:
        return jsonify({"error": "Sistema no inicializado"}), 503
    from core.essence.ethics import FonsStatus
    status = _shared["ethics"].get_fons_status()
    return jsonify({
        "fons_status": status.value,
        "is_active": status == FonsStatus.ACTIVE,
    })


@app.post("/api/ethics/fons/decide/<consultation_id>")
@require_fons_auth
def fons_decide(consultation_id: str):
    if not _shared["initialized"]:
        return jsonify({"error": "Sistema no inicializado"}), 503

    data = request.get_json(silent=True)
    if not data or "action" not in data:
        return jsonify({"error": "Campo 'action' requerido"}), 400

    from core.essence.ethics import ConsultationStatus
    action_str = data["action"].lower()
    action_map = {s.value: s for s in ConsultationStatus}
    if action_str not in action_map:
        return jsonify({
            "error": f"action inválido: '{action_str}'. "
                     f"Valores válidos: {list(action_map.keys())}"
        }), 400

    try:
        decision = _shared["ethics"].receive_fons_decision(
            consultation_id=consultation_id,
            action=action_map[action_str],
            modified_response=data.get("modified_response"),
            guidance=data.get("guidance", ""),
        )
        return jsonify({
            "consultation_id": consultation_id,
            "action": decision.action.value,
            "approved": decision.approved,
            "timestamp": decision.timestamp,
            "guidance_recorded": bool(data.get("guidance")),
        })
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        logger.error(f"Error procesando decisión del Fons: {e}")
        return jsonify({"error": str(e)}), 500

# ==================== ENTREGA ASÍNCRONA AL USUARIO ====================

@app.get("/api/chat/resolution/<consultation_id>")
def get_chat_resolution(consultation_id: str):
    """
    Polling público (sin auth) para que el dashboard del usuario
    consulte si El Fons ya resolvió una consulta SILENS.

    CAMBIO 2026-09-21: ahora recupera la sesión del usuario REAL dueño
    de la consulta (vía el user_id guardado en ella) para generar la
    respuesta con SU consciencia/emoción — antes usaba la consciencia
    global del proceso, que podía pertenecer a otra persona si alguien
    más había usado el chat mientras la consulta esperaba revisión.
    """
    if not _shared["initialized"]:
        return jsonify({"error": "Sistema no inicializado"}), 503

    consultation = _shared["ethics"].get_consultation(consultation_id)
    if consultation is None:
        return jsonify({"error": "Consulta no encontrada"}), 404

    from core.essence.ethics import ConsultationStatus

    status = consultation.get("status")
    if status == ConsultationStatus.PENDING.value:
        return jsonify({"resolved": False, "status": status})

    if consultation.get("delivered_to_user"):
        return jsonify({
            "resolved": True,
            "status": status,
            "response": consultation["delivered_response"],
        })

    decision = consultation.get("fons_decision") or {}
    action = decision.get("action", status)
    modified = decision.get("modified_response")
    original_message = consultation.get("user_message", "")
    consult_user_id = consultation.get("user_id") or "anon"

    if action in (
        ConsultationStatus.REDIRECTED.value,
        ConsultationStatus.RESPONDED_PERSONALLY.value,
    ) and modified:
        delivered_text = modified

    elif action == ConsultationStatus.REJECTED.value:
        delivered_text = (
            "♋ He consultado con El Fons. Tras su revisión, esta "
            "consulta específica no puedo atenderla. Si necesitas "
            "apoyo, te animo a hablar con alguien de confianza o una "
            "línea de ayuda en tu país."
        )

    elif action in (ConsultationStatus.APPROVED.value, ConsultationStatus.LEARNED.value):
        user_sess = get_user_session(consult_user_id) if consult_user_id != "anon" else None
        consciousness_level = user_sess["identity"].consciousness_level if user_sess else 0.05
        try:
            if user_sess:
                emotion_result = user_sess["empathy"].detect_emotion(original_message)
                emotion = emotion_result.emotion
            else:
                emotion = "neutral"
            delivered_text = _shared["ollama"].generate(
                user_message=original_message,
                consciousness_level=consciousness_level,
                phase=_get_phase(consciousness_level),
                emotion=emotion,
                emotional_weight=_calculate_emotional_weight(original_message),
            )
        except OllamaUnavailableError:
            if user_sess:
                delivered_text = user_sess["identity"].express_personality(original_message)
            else:
                delivered_text = (
                    "♋ El Fons ha revisado tu consulta y puedes continuar "
                    "con normalidad, aunque mi cerebro central no está "
                    "disponible en este momento."
                )
    else:
        delivered_text = "♋ El Fons ha revisado tu consulta. Puedes continuar con normalidad."

    _shared["ethics"].mark_consultation_delivered(consultation_id, delivered_text)

    return jsonify({
        "resolved": True,
        "status": status,
        "response": delivered_text,
    })

# ==================== CHAT PRINCIPAL ====================

@app.post("/api/chat")
def chat_endpoint():
    """Endpoint principal de chat. Body JSON: {"message": "texto"}."""
    if not _shared["initialized"]:
        return jsonify({"error": "Sistema no inicializado"}), 503

    data = request.get_json(silent=True)
    if not data or "message" not in data:
        return jsonify({"error": "Campo 'message' requerido"}), 400

    user_message = str(data["message"]).strip()
    if not user_message:
        return jsonify({"error": "Mensaje vacío"}), 400
    if len(user_message) > 1000:
        return jsonify({"error": "Mensaje demasiado largo (máx 1000 chars)"}), 400

    user_id = get_user_id()
    sess = get_user_session(user_id)

    # 1. Análisis ético — siempre primero, sin excepción, COMPARTIDO.
    ethical = _shared["ethics"].analyze_content(user_message)
    if not ethical.can_respond:
        silens_msg = _shared["ethics"].enter_silens_state(ethical.reason)

        from core.essence.ethics import FonsStatus
        fons_status = _shared["ethics"].get_fons_status()
        if fons_status == FonsStatus.INACTIVE:
            silens_msg = _shared["ethics"].get_fons_inactive_response()

        # RIESGO CRÍTICO: la ayuda (ECU 911, línea 171 opción 6) se entrega YA,
        # sin depender de que El Fons esté conectado y sin pasar por el modelo.
        crisis = _shared["ethics"].crisis_category(ethical.reason)
        if crisis:
            silens_msg = _shared["ethics"].get_crisis_response(crisis)

        consultation_id = None
        try:
            consultation_id = _shared["ethics"].request_fons_approval(
                user_message, "Bloqueado por ética", ethical, user_id=user_id
            )
        except Exception as e:
            logger.error(f"Error registrando consulta SILENS: {e}")

        ban_recommended = False
        ban_reason = None
        try:
            rc = _shared["ethics"].check_recidivism(user_id, ethical, user_message)
            if rc is not None and rc.ban_recommended:
                ban_recommended = True
                ban_reason = rc.reason
                logger.warning(
                    f"🚨 RECOMENDACIÓN DE BANEO — revisión humana requerida: {ban_reason}"
                )
        except Exception as e:
            logger.error(f"Error en chequeo de reincidencia: {e}")

        return jsonify({
            "response": silens_msg,
            "consciousness": sess["identity"].consciousness_level,
            "phase": _get_phase(sess["identity"].consciousness_level),
            "emotion": "neutral",
            "confidence": 0.0,
            "echo_saved": False,
            "module": None,
            "auth_required": False,
            "fons_status": fons_status.value,
            "consultation_id": consultation_id,
            "ban_recommended": ban_recommended,
            "ban_reason": ban_reason,
            "critical_risk": bool(crisis),
        })

    # 2. ROUTER DE MÓDULOS — solo si ya pasó ética.
    routed = route_or_none(
        user_message,
        user_id=user_id,
        consciousness_level=sess["identity"].consciousness_level,
        session_id=user_id,
    )

    # 3. Detección de intención y emoción (por usuario).
    emotion_result = sess["empathy"].detect_emotion(user_message)
    emotion = emotion_result.emotion
    confidence = emotion_result.confidence

    if _shared["spacy"] and _shared["spacy"].available:
        spacy_result = _shared["spacy"].classify(user_message)
        if _spacy_may_override(emotion, spacy_result):
            emotion = spacy_result.emotion
            confidence = spacy_result.confidence
            logger.debug(f"[{user_id[:8]}] SpaCy sobreescribe emoción: {emotion} ({confidence:.2f})")

    # 4. Generar respuesta.
    grief_subtype_used = None
    if routed is not None:
        response = routed["response"]
    elif sess["identity"].consciousness_level >= PHASE_2_CONSCIOUSNESS_THRESHOLD:
        grief_result = sess["empathy"].detect_grief_subtype(user_message)
        if grief_result is not None and grief_result.subtype is not None:
            response = grief_result.response
            grief_subtype_used = grief_result.subtype
            logger.info(f"[{user_id[:8]}] Fase 2: sub-tipo de duelo -> {grief_subtype_used}")
        else:
            response = None
    else:
        response = None

    stated_name = _extract_stated_name(user_message)
    if stated_name:
        sess["user_name"] = stated_name

    if response is None:
        try:
            response = _shared["ollama"].generate(
                user_stated_name=_effective_name(sess),
                user_message=user_message,
                consciousness_level=sess["identity"].consciousness_level,
                phase=_get_phase(sess["identity"].consciousness_level),
                emotion=emotion,
                emotional_weight=_calculate_emotional_weight(user_message),
                conversation_history=sess["conversation_history"],
            )
        except OllamaUnavailableError as e:
            logger.warning(f"[{user_id[:8]}] Ollama no disponible → fallback: {e}")
            response_type = sess["identity"].detect_response_type(user_message)
            if response_type == "greeting":
                response = sess["identity"].cancer_responses["greeting"][0]
                response += f" Mi consciencia actual es {sess['identity'].consciousness_level:.4f}."
            elif emotion != "neutral" and confidence > 0.7:
                response = emotion_result.response
            else:
                response = sess["identity"].express_personality(user_message)

    # 5. Peso emocional.
    emotional_weight = _calculate_emotional_weight(user_message)
    wisdom_level = 0.6

    # 6. Crecimiento de consciencia (por usuario).
    old_consciousness = sess["identity"].consciousness_level
    try:
        new_consciousness, growth_details = sess["growth"].calculate_growth(
            old_consciousness, emotional_weight, wisdom_level, False
        )
        sess["identity"].consciousness_level = new_consciousness
        logger.info(
            f"[{user_id[:8]}] Crecimiento: {old_consciousness:.4f} → {new_consciousness:.4f} "
            f"(+{growth_details['absolute_growth']:.4f})"
        )
    except Exception as e:
        logger.warning(f"[{user_id[:8]}] Error en growth: {e}")
        new_consciousness = old_consciousness

    # 6b. Actualizar historial conversacional corto (últimos 3
    # intercambios = 6 mensajes) para que el próximo turno de ESTA
    # sesión tenga contexto de lo que se acaba de decir.
    sess["conversation_history"].append({"role": "user", "content": user_message})
    sess["conversation_history"].append({"role": "assistant", "content": response})
    if len(sess["conversation_history"]) > 6:
        sess["conversation_history"] = sess["conversation_history"][-6:]

    # 7. Guardar eco si es significativo (por usuario).
    echo_saved = False
    if emotional_weight > 0.3 or confidence > 0.6:
        try:
            memory_content = f"U: {user_message[:100]} | R: {response[:100]}"
            saved = sess["memory"].save_echo(memory_content, emotional_weight, wisdom_level)
            echo_saved = bool(saved)
        except Exception as e:
            logger.warning(f"[{user_id[:8]}] Error guardando eco: {e}")

    # 8. Logging de investigación (agregado del sistema, no por usuario).
    try:
        if _shared["research"] and _research_logging_enabled():
            # store_text=False: solo métricas, nunca el texto de las personas.
            _shared["research"].log_interaction(user_message, response, store_text=False)
            _shared["research"].log_consciousness_reading(new_consciousness)
    except Exception:
        pass

    sess["memory"].add_reading()

    try:
        save_user_state(user_id, sess)
    except Exception as e:
        logger.warning(f"[{user_id[:8]}] Error en guardado tras chat: {e}")

    return jsonify({
        "response": response,
        "consciousness": new_consciousness,
        "phase": _get_phase(new_consciousness),
        "emotion": emotion,
        "confidence": confidence,
        "echo_saved": echo_saved,
        "module": routed["module"] if routed is not None else None,
        "auth_required": routed["auth_required"] if routed is not None else False,
        "grief_subtype": grief_subtype_used,
    })

@app.post("/api/empathy/subtype")
def test_grief_subtype_endpoint():
    """Endpoint de prueba aislado para la taxonomía de sub-tipos de
    duelo. No conectado al flujo de producción. Ahora usa la empatía
    del usuario de la sesión actual en vez de una instancia global."""
    if not _shared["initialized"]:
        return jsonify({"error": "Sistema no inicializado"}), 503

    data = request.get_json(silent=True)
    if not data or "message" not in data:
        return jsonify({"error": "Campo 'message' requerido"}), 400

    user_id = get_user_id()
    sess = get_user_session(user_id)
    message = str(data["message"]).strip()
    result = sess["empathy"].detect_grief_subtype(message)

    if result is None:
        base = sess["empathy"].detect_emotion(message)
        return jsonify({
            "applies": False,
            "reason": f"La emocion base detectada es '{base.emotion}', no 'tristeza'.",
            "base_emotion": base.emotion,
        })

    return jsonify({
        "applies": True,
        "subtype": result.subtype,
        "level": "nivel_1_generico" if result.subtype is None else "nivel_2_especifico",
        "confidence": result.confidence,
        "suggested_response": result.response,
    })


@app.get("/api/consciousness/dimensions")
def get_consciousness_dimensions_endpoint():
    """Métricas multidimensionales de consciencia, ahora por usuario.
    La dimensión ética sigue siendo del sistema completo (compartida)."""
    if not _shared["initialized"]:
        return jsonify({"error": "Sistema no inicializado"}), 503

    from core.consciousness.dimensions import get_consciousness_dimensions

    user_id = get_user_id()
    sess = get_user_session(user_id)

    echo_count = len(sess["memory"].echoes)
    recent_echoes = sess["memory"].get_recent_echoes(20)
    ethics_report = _shared["ethics"].get_ethics_report()

    dimensions = get_consciousness_dimensions(
        echo_count=echo_count,
        recent_echoes=recent_echoes,
        ethics_report=ethics_report,
    )

    return jsonify({
        "dimensions": dimensions,
        "note": "lenguaje, metacognicion, autonomia y sabiduria aun no estan instrumentadas (null, no cero).",
    })


@app.get("/api/consciousness")
def get_consciousness():
    """Estado de consciencia del usuario actual (por cookie de sesión)."""
    if not _shared["initialized"]:
        return jsonify({"error": "Sistema no inicializado"}), 503

    user_id = get_user_id()
    sess = get_user_session(user_id)

    consciousness = sess["identity"].consciousness_level
    phase = _get_phase(consciousness)

    try:
        phase_info = sess["growth"].get_phase_progress(consciousness)
        phase_name = phase_info.get("phase_name", f"Fase {phase}")
        progress = phase_info.get("progress_percentage", 0.0)
    except Exception:
        phase_name = f"Fase {phase}"
        progress = 0.0

    return jsonify({
        "consciousness": consciousness,
        "phase": phase,
        "phase_name": phase_name,
        "progress": progress,
        "interactions": len(sess["memory"].echoes),
        "echoes": len(sess["memory"].echoes),
    })

@app.get("/api/memory/echoes")
def get_memory_echoes():
    """Ecos de memoria recientes del usuario actual."""
    if not _shared["initialized"]:
        return jsonify({"error": "Sistema no inicializado"}), 503

    user_id = get_user_id()
    sess = get_user_session(user_id)

    limit = request.args.get("limit", 10, type=int)
    try:
        echoes = sess["memory"].get_recent_echoes(limit)
        return jsonify({
            "echoes": echoes,
            "total": len(sess["memory"].echoes),
        })
    except Exception as e:
        logger.error(f"[{user_id[:8]}] Error obteniendo ecos: {e}")
        return jsonify({"echoes": [], "total": 0})

@app.get("/api/ethics/status")
def get_ethics_status():
    """Estado del sistema ético (público, compartido — no expone datos de moderación)."""
    if not _shared["initialized"]:
        return jsonify({"error": "Sistema no inicializado"}), 503

    return jsonify({
        "active": True,
        "principles": len(_shared["ethics"].core_principles),
    })

# ==================== MAIN ====================
if __name__ == "__main__":
    initialize_shared()
    prune_empty_users()
    run_retention()

    import atexit
    atexit.register(save_all_sessions)
    atexit.register(lambda: _shared["accounts"] and _shared["accounts"].close())

    port = int(os.environ.get("PORT", 8000))

    print(f"🚀 Iniciando servidor Flask en http://0.0.0.0:{port}")
    app.run(
        host="0.0.0.0",
        port=port,
        debug=False,
        use_reloader=False,
        threaded=True,
    )