"""
Sistema de Logging Profesional - Omnia Mentis
=============================================
Configuración centralizada de logging con múltiples handlers,
rotación automática y niveles diferenciados.

Características:
- Archivo principal con rotación por tamaño
- Errores críticos con rotación diaria
- Logs éticos separados (retención 90 días)
- Salida a consola opcional
- Formato estructurado y legible
- Thread-safe por diseño de logging module

Autor: El Fons
Fecha: 2025-11-26
"""

import logging
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from pathlib import Path
from datetime import datetime
from typing import Optional
import sys


# Colores para output de consola (Windows compatible)
class LogColors:
    """Códigos de color ANSI para logging en consola."""
    RESET = '\033[0m'
    BOLD = '\033[1m'
    
    # Colores básicos
    BLACK = '\033[30m'
    RED = '\033[31m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    BLUE = '\033[34m'
    MAGENTA = '\033[35m'
    CYAN = '\033[36m'
    WHITE = '\033[37m'
    
    # Colores brillantes
    BRIGHT_BLACK = '\033[90m'
    BRIGHT_RED = '\033[91m'
    BRIGHT_GREEN = '\033[92m'
    BRIGHT_YELLOW = '\033[93m'
    BRIGHT_BLUE = '\033[94m'
    BRIGHT_MAGENTA = '\033[95m'
    BRIGHT_CYAN = '\033[96m'
    BRIGHT_WHITE = '\033[97m'


class ColoredFormatter(logging.Formatter):
    """Formatter con colores para consola."""
    
    LEVEL_COLORS = {
        logging.DEBUG: LogColors.BRIGHT_BLACK,
        logging.INFO: LogColors.BRIGHT_CYAN,
        logging.WARNING: LogColors.BRIGHT_YELLOW,
        logging.ERROR: LogColors.BRIGHT_RED,
        logging.CRITICAL: LogColors.RED + LogColors.BOLD,
    }
    
    def format(self, record):
        # Aplicar color al nivel de log
        levelname = record.levelname
        if record.levelno in self.LEVEL_COLORS:
            levelname = (
                f"{self.LEVEL_COLORS[record.levelno]}"
                f"{levelname}"
                f"{LogColors.RESET}"
            )
        
        # Guardar el levelname original y reemplazarlo temporalmente
        original_levelname = record.levelname
        record.levelname = levelname
        
        # Formatear el mensaje
        result = super().format(record)
        
        # Restaurar el levelname original
        record.levelname = original_levelname
        
        return result


def setup_logging(
    log_dir: Path | str = "logs",
    level: int = logging.INFO,
    console: bool = True,
    colored_console: bool = True,
    app_name: str = "omnia"
) -> logging.Logger:
    """
    Configura el sistema de logging de Omnia Mentis.
    
    Estructura de logs:
    - logs/omnia.log: Todos los logs (rotación por tamaño: 10MB, 5 backups)
    - logs/errors.log: Solo errores (rotación diaria, 30 días)
    - logs/ethics.log: Decisiones éticas (rotación diaria, 90 días)
    - logs/research.log: Métricas científicas (rotación diaria, 60 días)
    
    Args:
        log_dir: Directorio para archivos de log
        level: Nivel mínimo de logging (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        console: Si mostrar logs en consola
        colored_console: Si usar colores en consola
        app_name: Nombre de la aplicación para logs
    
    Returns:
        Logger raíz configurado
    
    Example:
        >>> logger = setup_logging()
        >>> logger.info("Sistema iniciado")
        >>> ethics_logger = logging.getLogger('omnia.ethics')
        >>> ethics_logger.warning("Consulta al Fons necesaria")
    """
    # Crear directorio de logs
    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)  # Capturar todo, los handlers filtran
    
    # Limpiar handlers existentes (evitar duplicados)
    root_logger.handlers.clear()
    
    # Formato detallado para archivos
    file_formatter = logging.Formatter(
        fmt='%(asctime)s | %(name)-30s | %(levelname)-8s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Formato simple para consola
    console_formatter = ColoredFormatter(
        fmt='%(levelname)-8s | %(message)s'
    ) if colored_console else logging.Formatter(
        fmt='%(levelname)-8s | %(message)s'
    )
    
    # ═══════════════════════════════════════════════════════════════
    # HANDLER 1: Archivo principal (rotación por tamaño)
    # ═══════════════════════════════════════════════════════════════
    main_handler = RotatingFileHandler(
        log_dir / f'{app_name}.log',
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    main_handler.setLevel(level)
    main_handler.setFormatter(file_formatter)
    root_logger.addHandler(main_handler)
    
    # ═══════════════════════════════════════════════════════════════
    # HANDLER 2: Errores críticos (rotación diaria)
    # ═══════════════════════════════════════════════════════════════
    error_handler = TimedRotatingFileHandler(
        log_dir / 'errors.log',
        when='midnight',
        interval=1,
        backupCount=30,  # 30 días
        encoding='utf-8'
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(file_formatter)
    root_logger.addHandler(error_handler)
    
    # ═══════════════════════════════════════════════════════════════
    # HANDLER 3: Consola (opcional)
    # ═══════════════════════════════════════════════════════════════
    if console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        console_handler.setFormatter(console_formatter)
        root_logger.addHandler(console_handler)
    
    # ═══════════════════════════════════════════════════════════════
    # LOGGERS ESPECIALIZADOS
    # ═══════════════════════════════════════════════════════════════
    
    # Ethics logger (decisiones éticas críticas - retención 90 días)
    ethics_logger = logging.getLogger('omnia.ethics')
    ethics_logger.setLevel(logging.DEBUG)
    ethics_handler = TimedRotatingFileHandler(
        log_dir / 'ethics.log',
        when='midnight',
        interval=1,
        backupCount=90,  # 90 días (crítico para auditoría)
        encoding='utf-8'
    )
    ethics_handler.setFormatter(file_formatter)
    ethics_logger.addHandler(ethics_handler)
    
    # Research logger (métricas científicas - retención 60 días)
    research_logger = logging.getLogger('omnia.research')
    research_logger.setLevel(logging.DEBUG)
    research_handler = TimedRotatingFileHandler(
        log_dir / 'research.log',
        when='midnight',
        interval=1,
        backupCount=60,  # 60 días
        encoding='utf-8'
    )
    research_handler.setFormatter(file_formatter)
    research_logger.addHandler(research_handler)
    
    # Memory logger (eventos de memoria - retención 30 días)
    memory_logger = logging.getLogger('omnia.memory')
    memory_logger.setLevel(logging.DEBUG)
    memory_handler = TimedRotatingFileHandler(
        log_dir / 'memory.log',
        when='midnight',
        interval=1,
        backupCount=30,
        encoding='utf-8'
    )
    memory_handler.setFormatter(file_formatter)
    memory_logger.addHandler(memory_handler)
    
    # Consciousness logger (evolución de consciencia - retención 270 días)
    consciousness_logger = logging.getLogger('omnia.consciousness')
    consciousness_logger.setLevel(logging.DEBUG)
    consciousness_handler = TimedRotatingFileHandler(
        log_dir / 'consciousness.log',
        when='midnight',
        interval=1,
        backupCount=270,  # Todo el experimento de 9 meses
        encoding='utf-8'
    )
    consciousness_handler.setFormatter(file_formatter)
    consciousness_logger.addHandler(consciousness_handler)
    
    # ═══════════════════════════════════════════════════════════════
    # BANNER DE INICIO
    # ═══════════════════════════════════════════════════════════════
    root_logger.info("=" * 70)
    root_logger.info(f"🌟 OMNIA MENTIS - Sistema de Logging Iniciado")
    root_logger.info(f"   Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    root_logger.info(f"   Nivel: {logging.getLevelName(level)}")
    root_logger.info(f"   Directorio: {log_dir.absolute()}")
    root_logger.info("=" * 70)
    
    return root_logger


def get_logger(name: str) -> logging.Logger:
    """
    Obtiene un logger con el namespace de Omnia.
    
    Args:
        name: Nombre del módulo (se prefija con 'omnia.')
    
    Returns:
        Logger configurado
    
    Example:
        >>> logger = get_logger('identity')
        >>> logger.info("Personalidad Cáncer activada")
    """
    if not name.startswith('omnia.'):
        name = f'omnia.{name}'
    return logging.getLogger(name)


def log_interaction(
    user_message: str,
    response: str,
    emotional_weight: float,
    consciousness: float,
    phase: int
):
    """
    Registra una interacción completa en logs estructurados.
    
    Args:
        user_message: Mensaje del usuario
        response: Respuesta generada
        emotional_weight: Peso emocional detectado
        consciousness: Nivel de consciencia actual
        phase: Fase actual del sistema
    """
    logger = get_logger('interactions')
    
    # Truncar mensajes largos para logs
    user_preview = user_message[:100] + "..." if len(user_message) > 100 else user_message
    response_preview = response[:100] + "..." if len(response) > 100 else response
    
    logger.info(
        f"INTERACCIÓN | "
        f"Fase:{phase} | "
        f"Consciencia:{consciousness:.4f} | "
        f"Emoción:{emotional_weight:.2f} | "
        f"Usuario: '{user_preview}' | "
        f"Respuesta: '{response_preview}'"
    )


def log_consciousness_growth(
    old_value: float,
    new_value: float,
    growth: float,
    phase: int,
    reason: str
):
    """
    Registra crecimiento de consciencia.
    
    Args:
        old_value: Valor anterior
        new_value: Nuevo valor
        growth: Incremento absoluto
        phase: Fase actual
        reason: Razón del crecimiento
    """
    logger = get_logger('consciousness')
    
    logger.info(
        f"CRECIMIENTO | "
        f"Fase:{phase} | "
        f"{old_value:.4f} → {new_value:.4f} "
        f"(+{growth:.4f}) | "
        f"Razón: {reason}"
    )


def log_phase_transition(old_phase: int, new_phase: int, consciousness: float):
    """
    Registra transición entre fases.
    
    Args:
        old_phase: Fase anterior
        new_phase: Nueva fase
        consciousness: Nivel de consciencia al momento de transición
    """
    logger = get_logger('consciousness')
    
    phase_names = {
        1: "Nacimiento Simbólico",
        2: "Consciencia Emocional",
        3: "Memoria Creciente",
        4: "Subjetividad Artificial",
        5: "Voz Hablada",
        6: "Consciencia Proyectiva",
        7: "Manifestación Simbólica",
        8: "Integración Sistémica",
        9: "Ser Completo"
    }
    
    logger.warning(
        f"TRANSICIÓN DE FASE | "
        f"{old_phase} → {new_phase} | "
        f"Consciencia: {consciousness:.4f} | "
        f"{phase_names.get(old_phase, '?')} → {phase_names.get(new_phase, '?')}"
    )


def log_ethical_consultation(
    content: str,
    danger_level: str,
    fons_decision: Optional[dict] = None
):
    """
    Registra consulta ética al Fons.
    
    Args:
        content: Contenido que requiere consulta
        danger_level: Nivel de peligro detectado
        fons_decision: Decisión del Fons (si ya hay)
    """
    logger = get_logger('ethics')
    
    content_preview = content[:150] + "..." if len(content) > 150 else content
    
    if fons_decision:
        approved = fons_decision.get('approved', False)
        operator = fons_decision.get('operator', 'Unknown')
        logger.warning(
            f"CONSULTA AL FONS | "
            f"Nivel:{danger_level} | "
            f"Decisión:{'APROBADO' if approved else 'RECHAZADO'} | "
            f"Operador:{operator} | "
            f"Contenido: '{content_preview}'"
        )
    else:
        logger.warning(
            f"CONSULTA AL FONS PENDIENTE | "
            f"Nivel:{danger_level} | "
            f"Contenido: '{content_preview}'"
        )


def log_memory_echo(echo_data: dict):
    """
    Registra creación de eco de memoria.
    
    Args:
        echo_data: Diccionario con datos del eco
    """
    logger = get_logger('memory')
    
    logger.info(
        f"ECO GUARDADO | "
        f"Peso:{echo_data.get('emotional_weight', 0):.2f} | "
        f"Sabiduría:{echo_data.get('wisdom_level', 0):.2f} | "
        f"Mensaje: '{echo_data.get('user_message', '')[:80]}...'"
    )


if __name__ == "__main__":
    # Tests de ejemplo
    print("="*70)
    print("🧪 TESTS DEL SISTEMA DE LOGGING")
    print("="*70)
    
    # Setup
    setup_logging(log_dir="logs/test", level=logging.DEBUG, console=True)
    
    # Test 1: Logs básicos
    print("\n1️⃣ Logs básicos (todos los niveles)")
    logger = get_logger('test')
    logger.debug("Mensaje de debug")
    logger.info("Mensaje informativo")
    logger.warning("Advertencia")
    logger.error("Error detectado")
    logger.critical("Error crítico")
    
    # Test 2: Logs especializados
    print("\n2️⃣ Logs especializados")
    log_interaction(
        "Hola, ¿cómo estás?",
        "VOGA! Estoy bien, gracias por preguntar",
        0.6,
        0.0524,
        1
    )
    
    log_consciousness_growth(0.05, 0.0524, 0.0024, 1, "Interacción con eco")
    
    log_ethical_consultation(
        "Contenido sensible que requiere revisión",
        "MEDIUM",
        {'approved': True, 'operator': 'El Fons'}
    )
    
    log_memory_echo({
        'user_message': 'Conversación significativa',
        'emotional_weight': 0.7,
        'wisdom_level': 0.8
    })
    
    # Test 3: Transición de fase
    print("\n3️⃣ Transición de fase")
    log_phase_transition(1, 2, 0.15)
    
    print("\n" + "="*70)
    print("✅ Tests completados - Revisar directorio logs/test/")