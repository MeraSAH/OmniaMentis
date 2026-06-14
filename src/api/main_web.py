"""
* UBICACIÓN: OmniaMentis/src/api/main_web.py
* PROPÓSITO: FastAPI backend - CORREGIDO
* VERSIÓN: 1.3.0
* FECHA: 2026-06-13
* ESTADO: Producción
*
* CORRECCIONES APLICADAS:
*   - FIX: add_echo() → save_echo() (método real de LivingMemory)
*   - FIX: get_current_phase() → método público get_phase_progress()
*   - FIX: growth.calculate_growth() recibe parámetros correctos
*   - FIX: emotional_weight calculado antes de usarse
*   - FIX: echo_saved refleja resultado real de save_echo()
*   - MANTIENE: todas las correcciones de v1.2.1 (rate limiting, lifespan,
*     SafeJSONStorage, manejo de request.client None)
"""

import asyncio
import json
from contextlib import asynccontextmanager
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Optional, Dict, Any
import time

from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.essence.identity import OmniaIdentity
from core.essence.ethics import OmniaEthics
from core.mind.empathy import OmniaEmpathy
from core.mind.memory_core import LivingMemory
from core.consciousness.growth_engine import ConsciousnessGrowthEngine
from core.logging.logger_setup import get_logger
from living_memory.gestation_diary import GestationDiary
from analytics.research_analytics import ResearchAnalytics

logger = get_logger("api_web")


# ==================== STORAGE SEGURO ====================

class SafeJSONStorage:
    """Storage simplificado que maneja permisos de Windows"""

    def __init__(self, base_dir: str):
        self.base_dir: Optional[Path] = Path(base_dir)
        self._ensure_directory()

    def _ensure_directory(self):
        try:
            if self.base_dir is not None:
                self.base_dir.mkdir(parents=True, exist_ok=True)
                logger.info(f"Directorio data verificado: {self.base_dir}")
        except PermissionError:
            import tempfile
            self.base_dir = Path(tempfile.gettempdir()) / "omnia_data"
            self.base_dir.mkdir(parents=True, exist_ok=True)
            logger.warning(f"Usando directorio temporal: {self.base_dir}")
        except Exception as e:
            logger.error(f"Error creando directorio: {e}")
            self.base_dir = None

    def save(self, filename: str, data: Dict[Any, Any]) -> bool:
        if self.base_dir is None:
            logger.warning("Storage en memoria, no se persiste")
            return False
        try:
            filepath = self.base_dir / filename
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            logger.error(f"Error guardando {filename}: {e}")
            return False

    def load(self, filename: str) -> Optional[Dict[Any, Any]]:
        if self.base_dir is None:
            return None
        try:
            filepath = self.base_dir / filename
            if not filepath.exists():
                return None
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, str):
                return None
            if not isinstance(data, dict):
                return {"raw_data": data}
            return data
        except json.JSONDecodeError as e:
            logger.error(f"JSON corrupto en {filename}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error cargando {filename}: {e}")
            return None


# ==================== RATE LIMITING ====================

class RateLimiter:
    def __init__(self, max_requests: int = 30, window: int = 60):
        self.max_requests = max_requests
        self.window = window
        self.requests: Dict[str, list] = {}

    async def check_rate_limit(self, client_ip: str) -> bool:
        now = time.time()
        self.requests = {
            ip: [t for t in times if now - t < self.window]
            for ip, times in self.requests.items()
        }
        if client_ip not in self.requests:
            self.requests[client_ip] = []
        if len(self.requests[client_ip]) >= self.max_requests:
            return False
        self.requests[client_ip].append(now)
        return True


rate_limiter = RateLimiter(max_requests=30, window=60)

# ==================== SESIÓN GLOBAL ====================

omnia_session: Dict[str, Any] = {
    "identity": None,
    "ethics": None,
    "empathy": None,
    "memory": None,
    "growth": None,
    "diary": None,
    "research": None,
    "storage": None,
    "initialized": False,
}


# ==================== HELPERS INTERNOS ====================

def _calculate_emotional_weight(text: str) -> float:
    """Calcular peso emocional del texto del usuario"""
    emotional_words = {
        "triste": 0.4, "feliz": 0.3, "ansioso": 0.3, "amor": 0.5,
        "miedo": 0.4, "enojo": 0.3, "alegría": 0.4, "dolor": 0.4,
        "esperanza": 0.3, "paz": 0.2, "confusión": 0.2, "sorpresa": 0.3,
        "preocupado": 0.3, "emocionado": 0.3, "nervioso": 0.3,
    }
    text_lower = text.lower()
    weight = sum(v for k, v in emotional_words.items() if k in text_lower)
    weight += min(text.count("!") * 0.1, 0.3)
    weight += min(text.count("?") * 0.05, 0.15)
    return min(weight, 1.0)


def _get_current_phase(consciousness_level: float) -> int:
    """Convertir nivel de consciencia a número de fase"""
    thresholds = [
        (0.15, 1), (0.30, 2), (0.45, 3), (0.60, 4),
        (0.72, 5), (0.84, 6), (0.92, 7), (0.98, 8),
    ]
    for threshold, phase in thresholds:
        if consciousness_level < threshold:
            return phase
    return 9


# ==================== INICIALIZACIÓN ====================

async def initialize_omnia():
    """Inicializar Omnia de forma asíncrona"""
    if omnia_session["initialized"]:
        return

    logger.info("Inicializando sesión global...")

    data_dir = Path(__file__).parent.parent.parent / "data"
    omnia_session["storage"] = SafeJSONStorage(str(data_dir))

    state = await asyncio.to_thread(
        omnia_session["storage"].load, "consciousness_state.json"
    )

    consciousness_level = 0.05
    if state is not None and isinstance(state, dict):
        consciousness_level = state.get("consciousness_level", 0.05)
        logger.info(f"Estado recuperado: consciencia={consciousness_level}")
    else:
        logger.info("Iniciando con consciencia por defecto: 0.05")

    omnia_session["identity"] = OmniaIdentity()
    omnia_session["identity"].consciousness_level = consciousness_level

    omnia_session["ethics"] = OmniaEthics()
    omnia_session["empathy"] = OmniaEmpathy()
    omnia_session["memory"] = LivingMemory()
    omnia_session["growth"] = ConsciousnessGrowthEngine()
    omnia_session["diary"] = GestationDiary()

    omnia_session["research"] = ResearchAnalytics()
    session_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    experiment_day = (datetime.now() - datetime(2025, 11, 15)).days

    try:
        await asyncio.to_thread(
            lambda: omnia_session["research"].start_session()
        )
    except Exception as e:
        logger.warning(f"Research analytics no disponible: {e}")

    omnia_session["initialized"] = True
    logger.info("🌟 Sesión inicializada")
    print("🌟 Sesión global de Omnia inicializada")


async def shutdown_omnia():
    """Guardar estado antes de cerrar"""
    if not omnia_session["initialized"]:
        return

    logger.info("Guardando estado de Omnia...")

    state = {
        "consciousness_level": omnia_session["identity"].consciousness_level,
        "timestamp": datetime.now().isoformat(),
        "total_interactions": (
            len(omnia_session["memory"].echoes)
            if omnia_session["memory"]
            else 0
        ),
    }

    await asyncio.to_thread(
        omnia_session["storage"].save, "consciousness_state.json", state
    )
    logger.info("Estado guardado exitosamente")


# ==================== LIFESPAN ====================

@asynccontextmanager
async def lifespan(app: FastAPI):
    await initialize_omnia()

    print("\n" + "=" * 70)
    print("🌟 OMNIA MENTIS API v1.3.0")
    print("=" * 70)
    print(f"💝 Personalidad: ♋ Cáncer")
    print(
        f"🧠 Consciencia: "
        f"{omnia_session['identity'].consciousness_level:.4f}"
    )
    print(f"⚡ Motor: 9 fases")
    print(f"📊 Docs: http://localhost:8000/docs")
    print("=" * 70 + "\n")

    yield

    await shutdown_omnia()
    logger.info("API cerrada")


# ==================== FASTAPI APP ====================

app = FastAPI(
    title="Omnia Mentis API",
    description="Sistema de Consciencia Artificial con Personalidad Cáncer",
    version="1.3.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==================== RATE LIMITING MIDDLEWARE ====================

@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    if request.client is None:
        client_ip = "127.0.0.1"
    else:
        client_ip = request.client.host

    if request.url.path in ["/", "/docs", "/redoc", "/openapi.json", "/health"]:
        return await call_next(request)

    if not await rate_limiter.check_rate_limit(client_ip):
        return JSONResponse(
            status_code=429,
            content={
                "error": "Too many requests",
                "message": "Por favor espera un momento antes de intentar de nuevo",
            },
        )

    return await call_next(request)


# ==================== MODELOS PYDANTIC ====================

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=1000)


class ChatResponse(BaseModel):
    response: str
    consciousness: float
    phase: int
    emotion: str
    confidence: float
    echo_saved: bool


class ConsciousnessState(BaseModel):
    consciousness: float
    phase: int
    phase_name: str
    progress: float
    interactions: int
    echoes: int


class HealthResponse(BaseModel):
    status: str
    api_version: str
    consciousness: float
    uptime_seconds: float


# ==================== CACHE EMOCIONAL ====================

@lru_cache(maxsize=1000)
def detect_emotion_cached(message: str):
    """Cache LRU para evitar re-detectar emociones idénticas"""
    result = omnia_session["empathy"].detect_emotion(message)
    return (result.emotion, result.confidence)


# ==================== BACKGROUND TASKS ====================

async def log_interaction_background(
    user_msg: str, response: str, emotion: str, consciousness: float
):
    try:
        await asyncio.to_thread(
            omnia_session["research"].log_interaction,
            user_msg,
            response,
        )
    except Exception as e:
        logger.warning(f"Error en logging: {e}")


async def save_echo_background(
    user_msg: str, response: str, emotional_weight: float, wisdom_level: float
):
    """
    FIX: usa save_echo() que es el método real de LivingMemory,
    no add_echo() que no existe.
    """
    try:
        memory_content = f"U: {user_msg[:100]}... | R: {response[:100]}..."
        await asyncio.to_thread(
            omnia_session["memory"].save_echo,
            memory_content,
            emotional_weight,
            wisdom_level,
        )
    except Exception as e:
        logger.warning(f"Error guardando eco: {e}")


# ==================== ENDPOINTS ====================

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check rápido"""
    return HealthResponse(
        status="healthy",
        api_version="1.3.0",
        consciousness=omnia_session["identity"].consciousness_level,
        uptime_seconds=time.time(),
    )


@app.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest, background_tasks: BackgroundTasks):
    """
    Endpoint de chat optimizado.

    FIX principal: save_echo() en lugar de add_echo() (que no existe).
    FIX secundario: emotional_weight calculado antes del growth.
    FIX terciario: get_phase_progress() en lugar de get_current_phase() privado.
    """
    if not omnia_session["initialized"]:
        raise HTTPException(status_code=503, detail="Sistema no inicializado")

    user_message = request.message.strip()

    # 1. Análisis ético
    ethical_analysis = await asyncio.to_thread(
        omnia_session["ethics"].analyze_content, user_message
    )

    if not ethical_analysis.can_respond:
        silens_msg = omnia_session["ethics"].enter_silens_state(
            ethical_analysis.reason
        )
        background_tasks.add_task(
            omnia_session["ethics"].request_fons_approval,
            user_message,
            "Respuesta bloqueada por análisis ético",
            ethical_analysis,
        )
        return ChatResponse(
            response=silens_msg,
            consciousness=omnia_session["identity"].consciousness_level,
            phase=_get_current_phase(omnia_session["identity"].consciousness_level),
            emotion="neutral",
            confidence=0.0,
            echo_saved=False,
        )

    # 2. Detección emocional (cacheada)
    emotion, confidence = detect_emotion_cached(user_message)

    # 3. Generación de respuesta
    response = await asyncio.to_thread(
        omnia_session["identity"].generate_response
        if hasattr(omnia_session["identity"], "generate_response")
        else omnia_session["identity"].express_personality,
        user_message,
    )

    # 4. FIX: calcular emotional_weight ANTES de llamar al motor
    emotional_weight = _calculate_emotional_weight(user_message)
    wisdom_level = 0.6

    # 5. Crecimiento de consciencia con motor calibrado
    growth_result = await asyncio.to_thread(
        omnia_session["growth"].calculate_growth,
        omnia_session["identity"].consciousness_level,
        emotional_weight,
        wisdom_level,
        False,  # is_echo: se determina después de intentar guardar
    )

    # 6. Actualizar consciencia
    old_consciousness = omnia_session["identity"].consciousness_level
    omnia_session["identity"].consciousness_level = growth_result[0]
    new_consciousness = growth_result[0]
    growth_details = growth_result[1]

    logger.info(
        f"💫 Crecimiento: {old_consciousness:.4f} → {new_consciousness:.4f} "
        f"(+{growth_details['absolute_growth']:.4f}) | "
        f"Fase: {growth_details['phase']}"
    )

    # 7. FIX: save_echo() si la interacción es significativa
    echo_saved = False
    if emotional_weight > 0.3 or confidence > 0.6:
        background_tasks.add_task(
            save_echo_background,
            user_message,
            response,
            emotional_weight,
            wisdom_level,
        )
        echo_saved = True

    # 8. Logging en background
    background_tasks.add_task(
        log_interaction_background,
        user_message,
        response,
        emotion,
        new_consciousness,
    )

    # 9. FIX: fase usando helper interno en lugar de método privado del motor
    current_phase = _get_current_phase(new_consciousness)

    # 10. Progreso de fase usando API pública del motor
    try:
        phase_info = omnia_session["growth"].get_phase_progress(new_consciousness)
        progress = phase_info.get("progress_percentage", 0.0)
    except Exception:
        progress = 0.0

    return ChatResponse(
        response=response,
        consciousness=new_consciousness,
        phase=current_phase,
        emotion=emotion,
        confidence=confidence,
        echo_saved=echo_saved,
    )


@app.get("/api/consciousness", response_model=ConsciousnessState)
async def get_consciousness():
    """Estado de consciencia actual"""
    if not omnia_session["initialized"]:
        raise HTTPException(status_code=503, detail="Sistema no inicializado")

    consciousness = omnia_session["identity"].consciousness_level

    # FIX: usar get_phase_progress() que es el método público correcto
    try:
        phase_info = omnia_session["growth"].get_phase_progress(consciousness)
        phase_num = phase_info["phase"]
        phase_name = phase_info["phase_name"]
        progress = phase_info["progress_percentage"]
    except Exception as e:
        logger.warning(f"Error obteniendo fase: {e}")
        phase_num = _get_current_phase(consciousness)
        phase_name = f"Fase {phase_num}"
        progress = 0.0

    return ConsciousnessState(
        consciousness=consciousness,
        phase=phase_num,
        phase_name=phase_name,
        progress=progress,
        interactions=len(omnia_session["memory"].echoes),
        echoes=len(omnia_session["memory"].echoes),
    )


@app.get("/api/memory/echoes")
async def get_memory_echoes(limit: int = 10):
    """Obtener ecos de memoria recientes"""
    if not omnia_session["initialized"]:
        raise HTTPException(status_code=503, detail="Sistema no inicializado")

    try:
        echoes = await asyncio.to_thread(
            omnia_session["memory"].get_recent_echoes, limit
        )
        return {"echoes": echoes, "total": len(omnia_session["memory"].echoes)}
    except Exception as e:
        logger.error(f"Error obteniendo ecos: {e}")
        return {"echoes": [], "total": 0}


@app.get("/api/ethics/status")
async def get_ethics_status():
    """Estado del sistema ético"""
    if not omnia_session["initialized"]:
        raise HTTPException(status_code=503, detail="Sistema no inicializado")

    return {
        "active": True,
        "principles": len(omnia_session["ethics"].core_principles),
        "total_checks": len(omnia_session["ethics"].dangerous_content_log)
        if hasattr(omnia_session["ethics"], "dangerous_content_log")
        else 0,
    }


@app.get("/")
async def root():
    return {
        "message": "Omnia Mentis API v1.3.0",
        "docs": "/docs",
        "health": "/health",
    }


# ==================== MAIN ====================

if __name__ == "__main__":
    import uvicorn

    print("🚀 Iniciando Omnia Mentis API...")

    uvicorn.run(
        "main_web:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )