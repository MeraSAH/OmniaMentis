"""
* UBICACIÓN: OmniaMentis/src/api/main_flask.py
* PROPÓSITO: API REST con Flask — orquesta ética, empatía, memoria,
*            crecimiento de consciencia, router de módulos, Ollama y
*            autenticación del panel del Fons + entrega asíncrona de
*            resoluciones al usuario final.
* DEPENDENCIAS: flask, flask-cors, requests (ver requirements_web.txt);
*            core.auth.fons_auth (stdlib only)
* CREADO: 2026-06-14
* ÚLTIMA MODIFICACIÓN: 2026-10-09
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
import threading
from pathlib import Path
from datetime import datetime, timedelta
from functools import wraps
from typing import Optional, Dict, Any

# ==================== PATH SETUP ====================
PROJECT_ROOT = Path(__file__).parent.parent.parent
SRC_PATH = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_PATH))

from flask import Flask, request, jsonify, Response, session
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
_cors_origins_raw = os.environ.get("CORS_ORIGINS", DEFAULT_CORS_ORIGINS)
_cors_origins = [o.strip() for o in _cors_origins_raw.split(",") if o.strip()]
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
    _rate_data[client_ip] = [
        t for t in _rate_data.get(client_ip, []) if now - t < window
    ]
    if len(_rate_data[client_ip]) >= max_req:
        return False
    _rate_data[client_ip].append(now)
    return True


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
    if "user_id" not in session:
        session.permanent = True
        session["user_id"] = str(uuid.uuid4())
    return session["user_id"]


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
        "user_name": None,
        "created_at": time.time(),
        "last_active": time.time(),
    }
    logger.info(f"[{user_id[:8]}] Sesión de usuario creada (consciencia={consciousness_level:.4f})")
    return sess


def get_user_session(user_id: str) -> Dict[str, Any]:
    """Obtiene (o crea, bajo lock) la sesión consciente de este usuario."""
    with _sessions_lock:
        sess = _user_sessions.get(user_id)
        if sess is None:
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
        save_user_state(user_id, sess)


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


def _start_autosave_thread() -> None:
    """Hilo en background: guarda TODOS los usuarios activos cada 60s,
    como red de seguridad independiente del guardado tras cada chat."""
    def _loop():
        while True:
            time.sleep(60)
            try:
                save_all_sessions()
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
    client_ip = request.remote_addr or "127.0.0.1"
    if not check_rate_limit(client_ip):
        return jsonify({
            "error": "Too many requests",
            "message": "Por favor espera un momento antes de intentar de nuevo"
        }), 429
    return None

# ==================== ENDPOINTS ====================

@app.get("/health")
def health_check():
    """Health check. Ya no expone una 'consciencia' única — con
    multiusuario no tendría sentido; expone cuántas sesiones hay
    activas en memoria en su lugar."""
    ollama_info = {"available": False, "error": "No inicializado"}
    spacy_available = False

    if _shared["initialized"]:
        ollama_info = _shared["ollama"].get_model_info()
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
            "model": "dolphin-phi:latest",
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
        if spacy_result.confidence > confidence and spacy_result.emotion != "neutral":
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
                user_stated_name=sess.get("user_name"),
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
        if _shared["research"]:
            _shared["research"].log_interaction(user_message, response)
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

    import atexit
    atexit.register(save_all_sessions)

    port = int(os.environ.get("PORT", 8000))

    print(f"🚀 Iniciando servidor Flask en http://0.0.0.0:{port}")
    app.run(
        host="0.0.0.0",
        port=port,
        debug=False,
        use_reloader=False,
        threaded=True,
    )