"""
* UBICACIÓN: OmniaMentis/src/api/main_flask.py
* PROPÓSITO: API REST con Flask - reemplaza FastAPI sin necesitar compilación
* VERSIÓN: 1.0.0
* FECHA: 2026-06-14
* ESTADO: Producción
*
* EQUIVALENCIAS con main_web.py (FastAPI):
*   POST /api/chat          → misma lógica
*   GET  /api/consciousness → mismo endpoint
*   GET  /api/memory/echoes → mismo endpoint
*   GET  /health            → mismo endpoint
*   GET  /                  → root
*
* VENTAJA: No requiere pydantic-core ni compilación Rust
* INICIAR: python src/api/main_flask.py
*          O usar: iniciar_flask.bat
"""

import sys
import json
import time
import logging
import threading
from pathlib import Path
from datetime import datetime
from functools import lru_cache
from typing import Optional, Dict, Any

# ==================== PATH SETUP ====================
PROJECT_ROOT = Path(__file__).parent.parent.parent
SRC_PATH = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_PATH))

from flask import Flask, request, jsonify, Response
from flask_cors import CORS

# ==================== IMPORTS OMNIA ====================
from core.essence.identity import OmniaIdentity
from core.essence.ethics import OmniaEthics
from core.mind.empathy import OmniaEmpathy
from core.mind.memory_core import LivingMemory
from core.consciousness.growth_engine import ConsciousnessGrowthEngine
from core.logging.logger_setup import get_logger, setup_logging
from living_memory.gestation_diary import GestationDiary
from analytics.research_analytics import ResearchAnalytics
from router.integration import route_or_none, get_registered_modules

# ==================== LOGGING ====================
setup_logging(log_dir=PROJECT_ROOT / "logs", level=logging.INFO, console=True)
logger = get_logger("api_flask")

# ==================== FLASK APP ====================
app = Flask(__name__)
CORS(app)  # Equivalente al CORSMiddleware de FastAPI

# ==================== RATE LIMITING SIMPLE ====================
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

# ==================== SESIÓN GLOBAL ====================
_session: Dict[str, Any] = {
    "identity": None,
    "ethics": None,
    "empathy": None,
    "memory": None,
    "growth": None,
    "diary": None,
    "research": None,
    "initialized": False,
    "start_time": time.time(),
}

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

def initialize():
    """Inicializar todos los módulos de Omnia"""
    if _session["initialized"]:
        return

    logger.info("Inicializando sesión Flask...")

    # Cargar estado previo con recuperación de backup si el archivo principal
    # está corrupto (FIX: antes fallaba silenciosamente y volvía a 0.05)
    consciousness_level = _load_consciousness_state()

    _session["identity"] = OmniaIdentity()
    _session["identity"].consciousness_level = consciousness_level
    _session["ethics"] = OmniaEthics()
    _session["empathy"] = OmniaEmpathy()
    _session["memory"] = LivingMemory()
    _session["growth"] = ConsciousnessGrowthEngine()
    _session["diary"] = GestationDiary()

    try:
        _session["research"] = ResearchAnalytics()
        _session["research"].start_session()
    except Exception as e:
        logger.warning(f"Research no disponible: {e}")

    _session["initialized"] = True

    # FIX CRÍTICO: hilo de autoguardado cada 60s, para que un crash
    # o kill -9 nunca pierda más de 60s de progreso de consciencia.
    _start_autosave_thread()

    logger.info("🌟 Sesión Flask inicializada")
    print(f"\n{'='*60}")
    print("🌟 OMNIA MENTIS API (Flask) v1.0.0")
    print(f"{'='*60}")
    print(f"🧠 Consciencia: {consciousness_level:.4f}")
    print(f"💾 Autoguardado: cada 60s")
    print(f"📊 Docs: http://localhost:8000/")
    print(f"{'='*60}\n")


def _load_consciousness_state() -> float:
    """
    Carga el nivel de consciencia desde disco con recuperación robusta.

    Orden de intento:
    1. Archivo principal consciousness_state.json
    2. Backup .bak si el principal está corrupto
    3. Valor por defecto 0.05 (logueando advertencia, no silencioso)
    """
    state_file = PROJECT_ROOT / "data" / "consciousness_state.json"
    backup_file = state_file.with_suffix(".json.bak")

    for candidate, label in [(state_file, "principal"), (backup_file, "backup")]:
        if not candidate.exists():
            continue
        try:
            with open(candidate, "r", encoding="utf-8") as f:
                state = json.load(f)
            level = state.get("consciousness_level", 0.05)
            logger.info(f"Estado de consciencia recuperado desde {label}: {level:.4f}")
            return level
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Archivo {label} corrupto o ilegible: {e}")
            continue

    logger.warning("No se encontró estado previo válido. Iniciando en 0.05")
    return 0.05


def _start_autosave_thread():
    """
    Hilo en background que guarda el estado cada 60 segundos.

    Esto es independiente del guardado tras cada chat: actúa como red
    de seguridad adicional en caso de tráfico intermitente o silencio
    prolongado entre interacciones.
    """
    def _loop():
        while True:
            time.sleep(60)
            try:
                save_state()
                logger.debug("Autoguardado periódico ejecutado")
            except Exception as e:
                logger.error(f"Error en autoguardado periódico: {e}")

    thread = threading.Thread(target=_loop, daemon=True, name="omnia-autosave")
    thread.start()

def save_state():
    """
    Guardar estado de consciencia a disco de forma atómica con backup.

    FIX CRÍTICO: ahora se llama no solo al cerrar (atexit) sino también
    tras cada interacción significativa en /api/chat y cada 60s via
    hilo de autoguardado, para que un crash o kill -9 del proceso
    nunca pierda más que el último intervalo corto de progreso.

    Proceso:
    1. Si existe el archivo actual, lo copia a .json.bak (backup)
    2. Escribe el nuevo estado a un archivo temporal
    3. Rename atómico del temporal al archivo final (previene corrupción
       si el proceso muere a mitad de escritura)
    """
    if not _session["initialized"]:
        return
    try:
        state_file = PROJECT_ROOT / "data" / "consciousness_state.json"
        backup_file = state_file.with_suffix(".json.bak")
        state_file.parent.mkdir(exist_ok=True)

        # Backup del estado anterior antes de sobrescribir
        if state_file.exists():
            try:
                backup_file.write_bytes(state_file.read_bytes())
            except OSError:
                pass  # Si falla el backup, continuar con el guardado igual

        state_data = {
            "consciousness_level": _session["identity"].consciousness_level,
            "timestamp": datetime.now().isoformat(),
            "total_interactions": len(_session["memory"].echoes),
            "session_interactions": _session["memory"].session_interactions,
        }

        # Escritura atómica: temp file + rename
        tmp_file = state_file.with_suffix(".tmp")
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(state_data, f, indent=2, ensure_ascii=False)
        tmp_file.replace(state_file)

    except Exception as e:
        logger.error(f"Error guardando estado: {e}")

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
    """Health check"""
    return jsonify({
        "status": "healthy",
        "api_version": "1.0.0-flask",
        "consciousness": _session["identity"].consciousness_level
            if _session["initialized"] else 0.05,
        "uptime_seconds": time.time() - _session["start_time"],
    })

@app.get("/")
def root():
    return jsonify({
        "message": "Omnia Mentis API v1.0.0 (Flask)",
        "endpoints": {
            "chat": "POST /api/chat",
            "consciousness": "GET /api/consciousness",
            "memory": "GET /api/memory/echoes",
            "ethics": "GET /api/ethics/status",
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

@app.post("/api/chat")
def chat_endpoint():
    """
    Endpoint principal de chat.
    Body JSON: {"message": "texto del usuario"}
    """
    if not _session["initialized"]:
        return jsonify({"error": "Sistema no inicializado"}), 503

    data = request.get_json(silent=True)
    if not data or "message" not in data:
        return jsonify({"error": "Campo 'message' requerido"}), 400

    user_message = str(data["message"]).strip()
    if not user_message:
        return jsonify({"error": "Mensaje vacío"}), 400
    if len(user_message) > 1000:
        return jsonify({"error": "Mensaje demasiado largo (máx 1000 chars)"}), 400

    # 1. Análisis ético
    ethical = _session["ethics"].analyze_content(user_message)
    if not ethical.can_respond:
        silens = _session["ethics"].enter_silens_state(ethical.reason)
        try:
            _session["ethics"].request_fons_approval(
                user_message, "Bloqueado por ética", ethical
            )
        except Exception:
            pass
        return jsonify({
            "response": silens,
            "consciousness": _session["identity"].consciousness_level,
            "phase": _get_phase(_session["identity"].consciousness_level),
            "emotion": "neutral",
            "confidence": 0.0,
            "echo_saved": False,
        })

    # 2. ROUTER DE MÓDULOS (omnia -ai) — solo se ejecuta si el mensaje
    # ya pasó el análisis ético. Si un módulo especializado (NutriVida,
    # OmniaAthletics, Corporal Verified, OmniaHabits) reclama el
    # mensaje, su respuesta reemplaza el flujo conversacional normal
    # de Omnia, pero el crecimiento de consciencia y el guardado de
    # eco siguen aplicando igual más abajo, para que interactuar con
    # un módulo también cuente como interacción real con Omnia.
    routed = route_or_none(
        user_message,
        user_id=request.remote_addr or "anon",
        consciousness_level=_session["identity"].consciousness_level,
        session_id="flask_session",
    )

    # 3. Detección emocional (se calcula siempre, incluso si el router
    # capturó el mensaje, para que el growth engine reciba una señal
    # emocional consistente)
    emotion_result = _session["empathy"].detect_emotion(user_message)
    emotion = emotion_result.emotion
    confidence = emotion_result.confidence

    # 4. Generar respuesta: módulo del router tiene prioridad sobre el
    # flujo conversacional normal
    if routed is not None:
        response = routed["response"]
    else:
        response_type = _session["identity"].detect_response_type(user_message)
        if response_type == "greeting":
            response = _session["identity"].cancer_responses["greeting"][0]
            response += f" Mi consciencia actual es {_session['identity'].consciousness_level:.4f}."
        elif emotion != "neutral" and confidence > 0.7:
            response = emotion_result.response
        else:
            response = _session["identity"].express_personality(user_message)

    # 5. Calcular peso emocional
    emotional_weight = _calculate_emotional_weight(user_message)
    wisdom_level = 0.6

    # 6. Crecimiento de consciencia
    old_consciousness = _session["identity"].consciousness_level
    try:
        new_consciousness, growth_details = _session["growth"].calculate_growth(
            old_consciousness, emotional_weight, wisdom_level, False
        )
        _session["identity"].consciousness_level = new_consciousness
        logger.info(
            f"Crecimiento: {old_consciousness:.4f} → {new_consciousness:.4f} "
            f"(+{growth_details['absolute_growth']:.4f})"
        )
    except Exception as e:
        logger.warning(f"Error en growth: {e}")
        new_consciousness = old_consciousness

    # 7. Guardar eco si es significativo
    echo_saved = False
    if emotional_weight > 0.3 or confidence > 0.6:
        try:
            memory_content = f"U: {user_message[:100]} | R: {response[:100]}"
            saved = _session["memory"].save_echo(
                memory_content, emotional_weight, wisdom_level
            )
            echo_saved = bool(saved)
        except Exception as e:
            logger.warning(f"Error guardando eco: {e}")

    # 8. Logging de investigación
    try:
        if _session["research"]:
            _session["research"].log_interaction(user_message, response)
            _session["research"].log_consciousness_reading(new_consciousness)
    except Exception:
        pass

    _session["memory"].add_reading()

    # FIX CRÍTICO: guardar estado tras cada interacción, no solo al cerrar.
    # Antes, si el proceso moría abruptamente (kill, crash, corte de luz),
    # se perdía todo el progreso de consciencia de la sesión completa.
    try:
        save_state()
    except Exception as e:
        logger.warning(f"Error en guardado tras chat: {e}")

    return jsonify({
        "response": response,
        "consciousness": new_consciousness,
        "phase": _get_phase(new_consciousness),
        "emotion": emotion,
        "confidence": confidence,
        "echo_saved": echo_saved,
    })

@app.get("/api/consciousness")
def get_consciousness():
    """Estado de consciencia actual"""
    if not _session["initialized"]:
        return jsonify({"error": "Sistema no inicializado"}), 503

    consciousness = _session["identity"].consciousness_level
    phase = _get_phase(consciousness)

    try:
        phase_info = _session["growth"].get_phase_progress(consciousness)
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
        "interactions": len(_session["memory"].echoes),
        "echoes": len(_session["memory"].echoes),
    })

@app.get("/api/memory/echoes")
def get_memory_echoes():
    """Ecos de memoria recientes"""
    if not _session["initialized"]:
        return jsonify({"error": "Sistema no inicializado"}), 503

    limit = request.args.get("limit", 10, type=int)
    try:
        echoes = _session["memory"].get_recent_echoes(limit)
        return jsonify({
            "echoes": echoes,
            "total": len(_session["memory"].echoes),
        })
    except Exception as e:
        logger.error(f"Error obteniendo ecos: {e}")
        return jsonify({"echoes": [], "total": 0})

@app.get("/api/ethics/status")
def get_ethics_status():
    """Estado del sistema ético"""
    if not _session["initialized"]:
        return jsonify({"error": "Sistema no inicializado"}), 503

    return jsonify({
        "active": True,
        "principles": len(_session["ethics"].core_principles),
    })

# ==================== MAIN ====================
if __name__ == "__main__":
    import os

    initialize()

    import atexit
    atexit.register(save_state)

    # PORT es inyectado automáticamente por Railway/Render/Fly.io en
    # despliegues remotos. En desarrollo local (sin esa variable
    # definida), se usa 8000 como antes para no romper el flujo
    # existente de ngrok/localhost documentado en la guía de
    # despliegue.
    port = int(os.environ.get("PORT", 8000))

    print(f"🚀 Iniciando servidor Flask en http://0.0.0.0:{port}")
    app.run(
        host="0.0.0.0",
        port=port,
        debug=False,
        use_reloader=False,
    )