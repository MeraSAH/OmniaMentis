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
from core.llm.ollama_client import OllamaClient, OllamaUnavailableError
from core.mind.spacy_intent import SpaCyIntentClassifier
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
    "ollama": None,       # OllamaClient — cerebro central dolphin-phi
    "spacy": None,        # SpaCyIntentClassifier — sistema nervioso
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

    # Cerebro central: Ollama con dolphin-phi
    # URL configurable por variable de entorno OLLAMA_URL
    import os
    ollama_url = os.environ.get("OLLAMA_URL", "http://localhost:11434")
    _session["ollama"] = OllamaClient(base_url=ollama_url)
    ollama_ok = _session["ollama"].is_available()
    if ollama_ok:
        logger.info(f"✅ Ollama disponible en {ollama_url} — cerebro activo")
    else:
        logger.warning(
            f"⚠️  Ollama NO disponible en {ollama_url}. "
            f"Usando fallback express_personality(). "
            f"Ejecutar: ollama serve && ollama pull dolphin-phi"
        )

    # Sistema nervioso: SpaCy lematización
    _session["spacy"] = SpaCyIntentClassifier()
    if _session["spacy"].available:
        logger.info("✅ SpaCy es_core_news_sm cargado — lematización activa")
    else:
        logger.warning(
            "⚠️  SpaCy no disponible. Usando detección por regex (OmniaEmpathy). "
            "Instalar: pip install spacy && python -m spacy download es_core_news_sm"
        )

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
    """Health check — incluye estado de Ollama y SpaCy."""
    ollama_info = {"available": False, "error": "No inicializado"}
    spacy_available = False

    if _session["initialized"]:
        ollama_info = _session["ollama"].get_model_info()
        spacy_available = _session["spacy"].available if _session["spacy"] else False

    return jsonify({
        "status": "healthy",
        "api_version": "2.0.0-flask",
        "consciousness": _session["identity"].consciousness_level
            if _session["initialized"] else 0.05,
        "uptime_seconds": time.time() - _session["start_time"],
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
    })

@app.get("/")
def root():
    return jsonify({
        "message": "Omnia Mentis API v1.0.0 (Flask)",
        "endpoints": {
            "chat": "POST /api/chat",
            "consciousness": "GET /api/consciousness",
            "memory": "GET /api/memory/echoes",
            "ethics_status": "GET /api/ethics/status",
            "ethics_pending": "GET /api/ethics/pending",
            "ethics_recidivism": "GET /api/ethics/recidivism/<user_id>",
            "fons_heartbeat": "POST /api/ethics/fons/heartbeat",
            "fons_status": "GET /api/ethics/fons/status",
            "fons_decide": "POST /api/ethics/fons/decide/<consultation_id>",
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

@app.get("/api/ethics/pending")
def get_ethics_pending():
    """
    Devuelve las consultas SILENS pendientes de revisión por el Fons.
    Este es el feed principal que el panel de administración del Fons
    debe consultar para ver qué necesita atención.
    """
    if not _session["initialized"]:
        return jsonify({"error": "Sistema no inicializado"}), 503
    try:
        consultations = _session["ethics"]._load_consultations()
        pending = [c for c in consultations if c.get("status") == "pending"]
        return jsonify({
            "pending_count": len(pending),
            "consultations": pending,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.get("/api/ethics/recidivism/<user_id>")
def get_recidivism(user_id: str):
    """
    Consulta el estado de reincidencia de un usuario específico.
    Útil para que el Fons evalúe el historial antes de tomar una
    decisión de baneo en Supabase. No registra ningún incidente nuevo.
    """
    if not _session["initialized"]:
        return jsonify({"error": "Sistema no inicializado"}), 503
    try:
        status = _session["ethics"].get_recidivism_status(user_id)
        return jsonify(status)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.post("/api/ethics/fons/heartbeat")
def fons_heartbeat():
    """
    El panel del Fons llama a este endpoint periódicamente para
    declararse activo. Sin llamadas recientes, el sistema asume que
    el Fons está INACTIVE y activa el fallback automático en SILENS.

    INTEGRACIÓN SUGERIDA: llamar a este endpoint desde el panel HTML
    del Fons cada 5 minutos vía setInterval(). Si el Fons cierra la
    pestaña o cierra sesión, el heartbeat deja de actualizarse y el
    timeout se activa automáticamente tras fons_inactive_timeout_minutes.
    """
    if not _session["initialized"]:
        return jsonify({"error": "Sistema no inicializado"}), 503
    try:
        _session["ethics"].fons_heartbeat()
        return jsonify({
            "status": "active",
            "timestamp": datetime.now().isoformat(),
            "timeout_minutes": _session["ethics"].fons_inactive_timeout_minutes,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.get("/api/ethics/fons/status")
def get_fons_status_endpoint():
    """Estado actual de disponibilidad del Fons (ACTIVE/INACTIVE)."""
    if not _session["initialized"]:
        return jsonify({"error": "Sistema no inicializado"}), 503
    from core.essence.ethics import FonsStatus
    status = _session["ethics"].get_fons_status()
    return jsonify({
        "fons_status": status.value,
        "is_active": status == FonsStatus.ACTIVE,
    })


@app.post("/api/ethics/fons/decide/<consultation_id>")
def fons_decide(consultation_id: str):
    """
    El Fons toma una decisión sobre una consulta SILENS pendiente.

    Body JSON:
    {
        "action": "approved|rejected|redirected|responded_personally|learned",
        "modified_response": "texto alternativo (obligatorio para redirected/responded_personally)",
        "guidance": "criterio ético a aprender (opcional)"
    }

    Este endpoint es el punto de integración entre el panel HTML del
    Fons y el sistema de auditoría de OmniaMentis. La decisión se
    persiste en fons_consultations.json con el estado correcto del
    documento SILENS/Fons. El baneo, si corresponde, lo ejecuta el
    Fons directamente en Supabase — este endpoint solo registra la
    decisión ética.
    """
    if not _session["initialized"]:
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
        decision = _session["ethics"].receive_fons_decision(
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

    # 1. Análisis ético — siempre primero, sin excepción.
    ethical = _session["ethics"].analyze_content(user_message)
    if not ethical.can_respond:
        # SILENS: redirige, nunca censura de forma diferente para el usuario.
        # El mensaje visible siempre es el mismo. Lo que varía internamente
        # es: (a) el estado del Fons determina la respuesta inmediata vs.
        # espera, y (b) se registra reincidencia para auditoría humana.
        silens_msg = _session["ethics"].enter_silens_state(ethical.reason)

        # Verificar si el Fons está activo o inactivo.
        # INACTIVE → respuesta de fallback inmediata (no dejar al usuario
        # en limbo indefinido). ACTIVE → SILENS normal (esperar revisión).
        from core.essence.ethics import FonsStatus
        fons_status = _session["ethics"].get_fons_status()
        if fons_status == FonsStatus.INACTIVE:
            silens_msg = _session["ethics"].get_fons_inactive_response()

        # Registrar consulta en el sistema de auditoría
        consultation_id = None
        try:
            user_ip = request.remote_addr or "anon"
            consultation_id = _session["ethics"].request_fons_approval(
                user_message, "Bloqueado por ética", ethical, user_id=user_ip
            )
        except Exception as e:
            logger.error(f"Error registrando consulta SILENS: {e}")

        # Seguimiento de reincidencia: invisible para el usuario, visible
        # para el Fons en el panel de moderación y vía campos JSON.
        ban_recommended = False
        ban_reason = None
        try:
            user_ip = request.remote_addr or "anon"
            rc = _session["ethics"].check_recidivism(
                user_ip, ethical, user_message
            )
            if rc is not None and rc.ban_recommended:
                ban_recommended = True
                ban_reason = rc.reason
                logger.warning(
                    f"🚨 RECOMENDACIÓN DE BANEO — revisión humana requerida: "
                    f"{ban_reason}"
                )
        except Exception as e:
            logger.error(f"Error en chequeo de reincidencia: {e}")

        return jsonify({
            "response": silens_msg,
            "consciousness": _session["identity"].consciousness_level,
            "phase": _get_phase(_session["identity"].consciousness_level),
            "emotion": "neutral",
            "confidence": 0.0,
            "echo_saved": False,
            "module": None,
            "auth_required": False,
            "fons_status": fons_status.value,
            "consultation_id": consultation_id,
            # Campos de moderación — consumibles por webhook de Supabase
            # o por el panel del Fons. NUNCA se muestran al usuario
            # final en el dashboard, solo los lee quien tenga acceso
            # a la respuesta cruda del backend.
            "ban_recommended": ban_recommended,
            "ban_reason": ban_reason,
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

    # 3. Detección de intención y emoción
    # SpaCy (lematización) tiene prioridad sobre OmniaEmpathy (regex),
    # pero ambos se ejecutan — SpaCy para clasificar, OmniaEmpathy como
    # fallback de respuesta cuando Ollama no está disponible.
    emotion_result = _session["empathy"].detect_emotion(user_message)
    emotion = emotion_result.emotion
    confidence = emotion_result.confidence

    if _session["spacy"] and _session["spacy"].available:
        spacy_result = _session["spacy"].classify(user_message)
        if spacy_result.confidence > confidence and spacy_result.emotion != "neutral":
            emotion = spacy_result.emotion
            confidence = spacy_result.confidence
            logger.debug(f"SpaCy sobreescribe emoción: {emotion} ({confidence:.2f})")

    # 4. Generar respuesta
    # Prioridad: módulo del router → Ollama → fallback express_personality()
    if routed is not None:
        response = routed["response"]
    else:
        # Intentar Ollama (cerebro central dolphin-phi)
        ollama_used = False
        try:
            response = _session["ollama"].generate(
                user_message=user_message,
                consciousness_level=_session["identity"].consciousness_level,
                phase=_get_phase(_session["identity"].consciousness_level),
                emotion=emotion,
                emotional_weight=_calculate_emotional_weight(user_message),
            )
            ollama_used = True
        except OllamaUnavailableError as e:
            logger.warning(f"Ollama no disponible → fallback: {e}")
            # Fallback: sistema rule-based anterior
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
        "module": routed["module"] if routed is not None else None,
        "auth_required": routed["auth_required"] if routed is not None else False,
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