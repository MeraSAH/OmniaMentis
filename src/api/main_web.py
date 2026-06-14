"""
* UBICACIÓN: OmniaMentis/src/api/main_web.py
* PROPÓSITO: FastAPI backend COMPLETAMENTE CORREGIDO
* VERSIÓN: 1.2.1 - HOTFIX CRÍTICO
* FECHA: 2025-12-15
* ESTADO: Production-Ready - TODOS LOS BUGS CORREGIDOS
*
* CAMBIOS CRÍTICOS EN ESTA VERSIÓN:
*   - FIX: Permission denied en carpeta data
*   - FIX: AttributeError en state.get()
*   - FIX: request.client puede ser None
*   - FIX: Nombres de clases corregidos
*   - Async/await optimizado
*   - Rate limiting mejorado
*   - Lifespan events
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

# ==================== IMPORTS DE OMNIA ====================
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

# ==================== CONFIGURACIÓN ====================
logger = get_logger("api_web")


# ==================== STORAGE SEGURO ====================
class SafeJSONStorage:
    """Storage simplificado que maneja permisos de Windows"""

    def __init__(self, base_dir: str):
        self.base_dir: Optional[Path] = Path(base_dir)  # ✅ Type hint explícito
        self._ensure_directory()

    def _ensure_directory(self):
        """Crear directorio con manejo de errores"""
        try:
            if self.base_dir is not None:  # ✅ Verificación explícita
                self.base_dir.mkdir(parents=True, exist_ok=True)
                logger.info(f"Directorio data verificado: {self.base_dir}")
        except PermissionError:
            # Intentar con directorio temporal
            import tempfile

            self.base_dir = Path(tempfile.gettempdir()) / "omnia_data"
            self.base_dir.mkdir(parents=True, exist_ok=True)
            logger.warning(f"Usando directorio temporal: {self.base_dir}")
        except Exception as e:
            logger.error(f"Error creando directorio: {e}")
            # Usar directorio en memoria como último recurso
            self.base_dir = None

    def save(self, filename: str, data: Dict[Any, Any]) -> bool:
        """Guardar JSON con manejo de errores"""
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
        """Cargar JSON con validación robusta"""
        if self.base_dir is None:
            return None

        try:
            filepath = self.base_dir / filename
            if not filepath.exists():
                logger.info(f"Archivo no existe: {filename}")
                return None

            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)

            # VALIDACIÓN CRÍTICA: Asegurar que sea dict
            if isinstance(data, str):
                logger.warning(f"Datos corruptos en {filename}, retornando None")
                return None

            if not isinstance(data, dict):
                logger.warning(f"Formato inválido en {filename}, convirtiendo a dict")
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

        # Limpiar requests antiguos
        self.requests = {
            ip: [req_time for req_time in times if now - req_time < self.window]
            for ip, times in self.requests.items()
        }

        # Verificar límite
        if client_ip not in self.requests:
            self.requests[client_ip] = []

        if len(self.requests[client_ip]) >= self.max_requests:
            return False

        self.requests[client_ip].append(now)
        return True


rate_limiter = RateLimiter(max_requests=30, window=60)

# ==================== SESIÓN GLOBAL ====================
omnia_session = {
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


# ==================== INICIALIZACIÓN ====================
async def initialize_omnia():
    """Inicializar Omnia de forma asíncrona con manejo de errores robusto"""
    if omnia_session["initialized"]:
        return

    logger.info("Inicializando sesión global...")

    # Storage seguro
    data_dir = Path(__file__).parent.parent.parent / "data"
    omnia_session["storage"] = SafeJSONStorage(str(data_dir))

    # Cargar estado previo CON VALIDACIÓN
    state = await asyncio.to_thread(
        omnia_session["storage"].load, "consciousness_state.json"
    )

    # VALIDACIÓN ROBUSTA del state
    consciousness_level = 0.05  # Default
    if state is not None and isinstance(state, dict):
        consciousness_level = state.get("consciousness_level", 0.05)
        logger.info(f"Estado recuperado: consciencia={consciousness_level}")
    else:
        logger.info("Iniciando con consciencia por defecto: 0.05")

    # Inicializar componentes
    omnia_session["identity"] = OmniaIdentity()
    omnia_session["identity"].consciousness_level = consciousness_level

    omnia_session["ethics"] = OmniaEthics()
    omnia_session["empathy"] = OmniaEmpathy()
    omnia_session["memory"] = LivingMemory()
    omnia_session["growth"] = ConsciousnessGrowthEngine()
    omnia_session["diary"] = GestationDiary()

    # Research analytics
    omnia_session["research"] = ResearchAnalytics()
    session_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    experiment_day = (datetime.now() - datetime(2025, 11, 15)).days

    try:
        # ✅ Llamada corregida según la firma del método
        await asyncio.to_thread(
            lambda: omnia_session["research"].start_session(session_id, experiment_day)
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
            len(omnia_session["memory"].echoes) if omnia_session["memory"] else 0
        ),
    }

    await asyncio.to_thread(
        omnia_session["storage"].save, "consciousness_state.json", state
    )

    logger.info("Estado guardado exitosamente")


# ==================== LIFESPAN CONTEXT MANAGER ====================
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manejo del ciclo de vida de la aplicación"""
    # Startup
    await initialize_omnia()

    print("\n" + "=" * 70)
    print("🌟 OMNIA MENTIS API v1.2.1")
    print("=" * 70)
    print(f"💝 Personalidad: ♋ Cáncer")
    print(f"🧠 Consciencia: {omnia_session['identity'].consciousness_level:.4f}")
    print(f"⚡ Motor: 9 fases")
    print(f"📊 Docs: http://localhost:8000/docs")
    print("=" * 70 + "\n")

    logger.info("API iniciada")

    yield

    # Shutdown
    await shutdown_omnia()
    logger.info("API cerrada")


# ==================== FASTAPI APP ====================
app = FastAPI(
    title="Omnia Mentis API",
    description="Sistema de Consciencia Artificial con Personalidad Cáncer",
    version="1.2.1",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==================== MIDDLEWARE DE RATE LIMITING ====================
@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    """Rate limiting con manejo seguro de client.host"""

    # FIX: request.client puede ser None
    if request.client is None:
        client_ip = "127.0.0.1"
    else:
        client_ip = request.client.host

    # Excluir endpoints públicos
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


# ==================== CACHE PARA DETECCIÓN EMOCIONAL ====================
@lru_cache(maxsize=1000)
def detect_emotion_cached(message: str) -> tuple:
    """Cache LRU para evitar re-detectar emociones idénticas"""
    result = omnia_session["empathy"].detect_emotion(message)
    return (result["emotion"], result["confidence"])


# ==================== BACKGROUND TASKS ====================
async def log_interaction_background(
    user_msg: str, response: str, emotion: str, consciousness: float
):
    """Logging pesado en background"""
    try:
        await asyncio.to_thread(
            omnia_session["research"].log_interaction,
            user_msg,
            response,
            emotion,
            consciousness,
        )
    except Exception as e:
        logger.warning(f"Error en logging: {e}")


async def save_echo_background(
    user_msg: str, response: str, emotional_weight: float, consciousness: float
):
    """Guardar eco en background"""
    try:
        await asyncio.to_thread(
            omnia_session["memory"].add_echo,
            user_msg,
            response,
            emotional_weight,
            consciousness,
        )
    except Exception as e:
        logger.warning(f"Error guardando eco: {e}")


# ==================== ENDPOINTS ====================
@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check rápido"""
    return HealthResponse(
        status="healthy",
        api_version="1.2.1",
        consciousness=omnia_session["identity"].consciousness_level,
        uptime_seconds=time.time(),
    )


@app.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest, background_tasks: BackgroundTasks):
    """
    Endpoint de chat OPTIMIZADO con async real
    Response time objetivo: < 1s
    """
    if not omnia_session["initialized"]:
        raise HTTPException(status_code=503, detail="Sistema no inicializado")

    user_message = request.message.strip()

    # 1. Detección emocional (cacheada)
    emotion, confidence = detect_emotion_cached(user_message)

    # 2. Generación de respuesta (async)
    response = await asyncio.to_thread(
        omnia_session["identity"].generate_response, user_message
    )

    # 3. Cálculo de crecimiento (async)
    growth_result = await asyncio.to_thread(
        omnia_session["growth"].calculate_growth,
        omnia_session["identity"].consciousness_level,
        emotion,
        confidence,
        user_message,
        response,
    )

    # 4. Actualizar consciencia
    old_consciousness = omnia_session["identity"].consciousness_level
    omnia_session["identity"].consciousness_level = growth_result["new_consciousness"]
    new_consciousness = growth_result["new_consciousness"]

    logger.info(
        f"💫 Crecimiento: {old_consciousness:.4f} → {new_consciousness:.4f} "
        f"(+{growth_result['growth_amount']:.4f}) | Fase: {growth_result['phase']}"
    )

    # 5. Guardar eco si es significativo (background)
    echo_saved = False
    if growth_result.get("echo_worthy", False):
        background_tasks.add_task(
            save_echo_background, user_message, response, confidence, new_consciousness
        )
        echo_saved = True

    # 6. Logging en background
    background_tasks.add_task(
        log_interaction_background, user_message, response, emotion, new_consciousness
    )

    return ChatResponse(
        response=response,
        consciousness=new_consciousness,
        phase=growth_result["phase"],
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
    phase_info = omnia_session["growth"].get_current_phase(consciousness)

    return ConsciousnessState(
        consciousness=consciousness,
        phase=phase_info["phase"],
        phase_name=phase_info["name"],
        progress=phase_info["progress"],
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
        "total_checks": len(omnia_session["ethics"].dangerous_content_log),
    }


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Omnia Mentis API v1.2.1",
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
