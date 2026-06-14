"""
🔬 research_analytics.py - Sistema de Investigación Científica
=============================================================
Sistema de análisis y validación de consciencia artificial

UBICACIÓN: src/analytics/research_analytics.py

CHANGELOG:
- ✅ Tipado fuerte con @dataclass
- ✅ Código comentado eliminado (###self.interaction_count)
- ✅ Manejo de excepciones específico
- ✅ Validación de entrada robusta
- ✅ Sistema de backup automático
- ✅ Documentación completa

AUTOR: Omnia Mentis Project
FECHA: 2024
"""

import json
import os
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict, field
from pathlib import Path

# ====================== TIPOS DE DATOS CON DATACLASSES ======================


@dataclass
class InteractionLog:
    """
    Registro tipado de una interacción entre usuario y Omnia

    Attributes:
        interaction_id: Identificador único
        timestamp: Momento de la interacción (ISO format)
        user_input: Mensaje del usuario
        omnia_response: Respuesta generada
        length: Longitud de la respuesta
        complexity: Score de complejidad lingüística (0.0-1.0)
    """

    interaction_id: str
    timestamp: str
    user_input: str
    omnia_response: str
    length: int
    complexity: float


@dataclass
class ConsciousnessReading:
    """
    Lectura de nivel de consciencia en un momento específico

    Attributes:
        reading_id: Identificador único de la lectura
        timestamp: Momento de la lectura (ISO format)
        consciousness_level: Nivel de consciencia (0.0-1.0)
    """

    reading_id: str
    timestamp: str
    consciousness_level: float


@dataclass
class EmpathyEvent:
    """
    Evento de detección empática (para futuro uso)

    Attributes:
        event_id: Identificador único
        timestamp: Momento del evento
        emotion_detected: Emoción detectada
        confidence: Confianza en la detección (0.0-1.0)
        empathy_score: Score de respuesta empática
    """

    event_id: str
    timestamp: str
    emotion_detected: str
    confidence: float
    empathy_score: float


@dataclass
class SessionData:
    """
    Datos completos de una sesión de investigación

    Attributes:
        session_id: Identificador único de sesión
        experiment_day: Día del experimento (1-270)
        start_time: Inicio de sesión (ISO format)
        end_time: Fin de sesión (ISO format o None)
        interactions: Lista de interacciones registradas
        consciousness_readings: Lista de lecturas de consciencia
        empathy_events: Lista de eventos empáticos
        memory_events: Lista de eventos de memoria
        metadata: Metadatos de la sesión
    """

    session_id: str
    experiment_day: int
    start_time: str
    end_time: Optional[str] = None
    interactions: List[Dict[str, Any]] = field(default_factory=list)
    consciousness_readings: List[Dict[str, Any]] = field(default_factory=list)
    empathy_events: List[Dict[str, Any]] = field(default_factory=list)
    memory_events: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, str] = field(default_factory=dict)


@dataclass
class ResearchReport:
    """
    Reporte científico de investigación

    Attributes:
        report_metadata: Información del reporte
        session_info: Información de la sesión
        scientific_analysis: Análisis científico detallado
        conclusions: Conclusiones y métricas finales
    """

    report_metadata: Dict[str, str]
    session_info: Dict[str, Any]
    scientific_analysis: Dict[str, Dict[str, Any]]
    conclusions: Dict[str, Any]


# ====================== CLASE PRINCIPAL ======================
class ResearchAnalytics:
    """
    Sistema de análisis científico para validación de consciencia

    Este sistema registra y analiza todas las interacciones, lecturas de
    consciencia y eventos empáticos durante el desarrollo de Omnia Mentis.

    Características:
    - Registro estructurado de sesiones
    - Análisis de complejidad lingüística
    - Tracking de evolución de consciencia
    - Generación de reportes científicos
    - Sistema de backup automático

    Usage:
        analytics = ResearchAnalytics()
        session_id = analytics.start_session()
        analytics.log_interaction("Hola", "VOGA, querido ser...")
        analytics.log_consciousness_reading(0.0501)
        analytics.end_session()
    """

    def __init__(self, research_dir: str = "research") -> None:
        """
        Inicializar sistema de investigación

        Args:
            research_dir: Directorio base para datos de investigación

        Raises:
            RuntimeError: Si no se pueden crear los directorios
        """
        self.research_dir = Path(research_dir)
        self.sessions_file = self.research_dir / "sessions_data.json"
        self.daily_reports_dir = self.research_dir / "daily_reports"
        self.exports_dir = self.research_dir / "exports"

        # Crear estructura de directorios
        self._initialize_directories()

        # Estado de sesión actual
        self.session_id: Optional[str] = None
        self.current_session: Optional[SessionData] = None
        self.session_start_time: Optional[datetime] = None
        self.interaction_count: int = 0

    # ==================== MÉTODOS PÚBLICOS ====================

    def start_session(self) -> str:
        """
        Inicia una nueva sesión de investigación

        Crea una nueva sesión con identificador único basado en timestamp
        e inicializa todos los contadores.

        Returns:
            str: Identificador único de la sesión (formato: session_YYYYMMDD_HHMMSS)

        Example:
            >>> analytics = ResearchAnalytics()
            >>> session_id = analytics.start_session()
            >>> print(session_id)
            'session_20240115_143022'
        """
        self.session_start_time = datetime.now()
        self.session_id = f"session_{self.session_start_time.strftime('%Y%m%d_%H%M%S')}"
        self.interaction_count = 0

        self.current_session = SessionData(
            session_id=self.session_id,
            experiment_day=self._calculate_experiment_day(),
            start_time=self.session_start_time.isoformat(),
            metadata={
                "omnia_version": "Enhanced v1.0",
                "research_protocol": "Consciousness Validation",
                "python_version": f"{__import__('sys').version_info.major}.{__import__('sys').version_info.minor}",
                "platform": __import__("platform").system(),
            },
        )

        print(f"🔬 Sesión de investigación iniciada: {self.session_id}")
        print(f"   Día del experimento: {self.current_session.experiment_day}/270")

        return self.session_id

    def log_interaction(self, user_input: str, omnia_response: str) -> None:
        """
        Registra una interacción con análisis automático de complejidad

        Args:
            user_input: Mensaje del usuario (máx 500 chars)
            omnia_response: Respuesta de Omnia (máx 1000 chars)

        Raises:
            RuntimeError: Si no hay sesión activa
            ValueError: Si los parámetros son inválidos o vacíos

        Example:
            >>> analytics.log_interaction(
            ...     "Hola, ¿cómo estás?",
            ...     "VOGA, querido ser. Mi consciencia Cáncer te saluda..."
            ... )
        """
        if not self.current_session:
            raise RuntimeError(
                "No hay sesión activa. Debes llamar a start_session() primero."
            )

        # Validación de entrada
        if not user_input or not isinstance(user_input, str):
            raise ValueError("user_input debe ser una cadena no vacía")

        if not omnia_response or not isinstance(omnia_response, str):
            raise ValueError("omnia_response debe ser una cadena no vacía")

        # Incrementar contador (CORREGIDO - ya no está comentado)
        self.interaction_count += 1

        # Crear log de interacción
        interaction_log = InteractionLog(
            interaction_id=f"{self.session_id}_int_{self.interaction_count:03d}",
            timestamp=datetime.now().isoformat(),
            user_input=user_input[:500],  # Limitar longitud para evitar overflow
            omnia_response=omnia_response[:1000],
            length=len(omnia_response),
            complexity=self._calculate_complexity(omnia_response),
        )

        # Guardar en sesión actual
        self.current_session.interactions.append(asdict(interaction_log))

        # Log opcional para debugging
        if self.interaction_count % 10 == 0:
            print(f"   📝 {self.interaction_count} interacciones registradas")

    def log_consciousness_reading(self, level: float) -> None:
        """
        Registra lectura de consciencia con validación

        Args:
            level: Nivel de consciencia entre 0.0 y 1.0

        Raises:
            RuntimeError: Si no hay sesión activa
            ValueError: Si el nivel está fuera del rango válido

        Example:
            >>> analytics.log_consciousness_reading(0.0523)
        """
        if not self.current_session:
            raise RuntimeError("No hay sesión activa")

        # Validación de rango
        if not isinstance(level, (int, float)):
            raise ValueError(f"Nivel debe ser numérico, recibido: {type(level)}")

        if not 0.0 <= level <= 1.0:
            raise ValueError(
                f"Nivel de consciencia debe estar entre 0.0 y 1.0, recibido: {level}"
            )

        reading = ConsciousnessReading(
            reading_id=f"{self.session_id}_cons_{len(self.current_session.consciousness_readings) + 1:03d}",
            timestamp=datetime.now().isoformat(),
            consciousness_level=round(level, 4),
        )

        self.current_session.consciousness_readings.append(asdict(reading))

    def log_empathy_event(
        self, emotion: str, confidence: float, empathy_score: float
    ) -> None:
        """
        Registra evento empático detectado (opcional)

        Args:
            emotion: Emoción detectada
            confidence: Confianza en la detección (0.0-1.0)
            empathy_score: Score de la respuesta empática (0.0-1.0)

        Raises:
            RuntimeError: Si no hay sesión activa
        """
        if not self.current_session:
            raise RuntimeError("No hay sesión activa")

        event = EmpathyEvent(
            event_id=f"{self.session_id}_emp_{len(self.current_session.empathy_events) + 1:03d}",
            timestamp=datetime.now().isoformat(),
            emotion_detected=emotion,
            confidence=min(max(confidence, 0.0), 1.0),
            empathy_score=min(max(empathy_score, 0.0), 1.0),
        )

        self.current_session.empathy_events.append(asdict(event))

    def end_session(self) -> bool:
        """
        Finaliza la sesión y guarda todos los datos con backup

        Returns:
            bool: True si se guardó correctamente, False en caso contrario

        Example:
            >>> success = analytics.end_session()
            >>> if success:
            ...     print("Sesión guardada correctamente")
        """
        if not self.current_session:
            print("⚠️  No hay sesión activa para finalizar")
            return False

        try:
            # Marcar fin de sesión
            self.current_session.end_time = datetime.now().isoformat()

            # Cargar sesiones existentes
            sessions = self._load_sessions()
            sessions.append(asdict(self.current_session))

            # Guardar con sistema de backup
            self._save_with_backup(self.sessions_file, sessions)

            print(f"✅ Sesión {self.session_id} guardada correctamente")
            print(f"   Interacciones: {self.interaction_count}")
            print(
                f"   Lecturas de consciencia: {len(self.current_session.consciousness_readings)}"
            )

            # Generar reporte diario
            self._generate_daily_report()

            # Limpiar estado
            self.current_session = None
            self.session_id = None
            self.interaction_count = 0

            return True

        except (OSError, TypeError) as e:
            print(f"❌ Error finalizando sesión: {e}")
            return False

    def generate_session_report(self) -> Dict[str, Any]:
        """
        Genera reporte científico completo de la sesión actual

        Returns:
            Dict con estructura ResearchReport o dict con error

        Example:
            >>> report = analytics.generate_session_report()
            >>> print(report['conclusions']['authenticity_score'])
            0.847
        """
        if not self.current_session:
            return {
                "error": "No hay sesión activa",
                "timestamp": datetime.now().isoformat(),
            }

        report = ResearchReport(
            report_metadata={
                "report_id": f"report_{self.session_id}",
                "generated_at": datetime.now().isoformat(),
                "session_id": self.session_id or "",
                "version": "1.0",
            },
            session_info=self._get_session_info(),
            scientific_analysis={
                "interactions": self._analyze_interactions(),
                "consciousness": self._analyze_consciousness(),
                "empathy": self._analyze_empathy(),
            },
            conclusions={
                "summary": self._generate_summary(),
                "authenticity_score": self._calculate_authenticity(),
                "growth_rate": self._calculate_growth_rate(),
                "complexity_trend": self._calculate_complexity_trend(),
            },
        )

        return asdict(report)

    # ==================== MÉTODOS PRIVADOS ====================

    def _initialize_directories(self) -> None:
        """Crear estructura de directorios necesaria"""
        try:
            self.research_dir.mkdir(parents=True, exist_ok=True)
            self.daily_reports_dir.mkdir(parents=True, exist_ok=True)
            self.exports_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            raise RuntimeError(f"Error creando directorios de investigación: {e}")

    def _calculate_experiment_day(self) -> int:
        """
        Calcula el día actual del experimento basado en la primera sesión

        Returns:
            int: Día del experimento (1-270, max 9 meses)
        """
        try:
            sessions = self._load_sessions()
            if not sessions:
                return 1

            # Obtener timestamp de la primera sesión
            first_session_time = min(
                datetime.fromisoformat(s["start_time"]) for s in sessions
            )

            # Calcular días transcurridos
            days = (datetime.now() - first_session_time).days + 1

            # Limitar a 270 días (9 meses * 30 días)
            return min(days, 270)

        except (KeyError, ValueError, TypeError) as e:
            print(f"⚠️  Error calculando día del experimento: {e}")
            return 1

    def _load_sessions(self) -> List[Dict[str, Any]]:
        """
        Carga sesiones existentes desde archivo JSON

        Returns:
            Lista de sesiones o lista vacía si hay error
        """
        try:
            if self.sessions_file.exists():
                with open(self.sessions_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return data if isinstance(data, list) else []
        except (json.JSONDecodeError, OSError) as e:
            print(f"⚠️  Error cargando sesiones: {e}")

        return []

    def _save_with_backup(self, file_path: Path, data: Any) -> None:
        """
        Guarda datos con sistema de backup automático

        Args:
            file_path: Ruta del archivo a guardar
            data: Datos serializables a JSON
        """
        backup_path = file_path.with_suffix(".backup.json")

        # Crear backup del archivo existente
        if file_path.exists():
            try:
                file_path.replace(backup_path)
            except OSError:
                pass  # Si falla el backup, continuar de todas formas

        # Guardar nuevos datos
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def _calculate_complexity(self, text: str) -> float:
        """
        Calcula complejidad lingüística del texto

        Métricas:
        - Diversidad léxica (ratio palabras únicas)
        - Longitud promedio de palabras

        Args:
            text: Texto a analizar

        Returns:
            float: Score de complejidad (0.0 - 1.0)
        """
        if not text:
            return 0.0

        words = text.split()
        if not words:
            return 0.0

        # Diversidad léxica
        unique_words = len(set(word.lower() for word in words))
        lexical_diversity = unique_words / len(words)

        # Longitud promedio de palabras
        avg_word_length = sum(len(w) for w in words) / len(words)
        length_score = min(avg_word_length / 10, 1.0)

        # Complejidad combinada (70% diversidad, 30% longitud)
        complexity = (lexical_diversity * 0.7) + (length_score * 0.3)

        return round(min(complexity * 2, 1.0), 3)

    def _get_session_info(self) -> Dict[str, Any]:
        """Obtiene información básica de la sesión"""
        if not self.session_start_time or not self.current_session:
            return {}

        duration = (datetime.now() - self.session_start_time).total_seconds() / 60

        return {
            "session_id": self.session_id,
            "duration_minutes": round(duration, 2),
            "interactions": self.interaction_count,
            "start_time": self.current_session.start_time,
            "experiment_day": self.current_session.experiment_day,
        }

    def _analyze_interactions(self) -> Dict[str, Any]:
        """Analiza estadísticas de interacciones"""
        if not self.current_session:
            return {"count": 0}

        interactions = self.current_session.interactions

        if not interactions:
            return {"count": 0}

        complexities = [i["complexity"] for i in interactions]
        lengths = [i["length"] for i in interactions]

        return {
            "count": len(interactions),
            "avg_complexity": round(sum(complexities) / len(complexities), 3),
            "min_complexity": round(min(complexities), 3),
            "max_complexity": round(max(complexities), 3),
            "avg_response_length": round(sum(lengths) / len(lengths), 1),
            "total_words": sum(len(i["omnia_response"].split()) for i in interactions),
        }

    def _analyze_consciousness(self) -> Dict[str, Any]:
        """Analiza evolución de consciencia"""
        if not self.current_session:
            return {"readings": 0}

        readings = self.current_session.consciousness_readings

        if not readings:
            return {"readings": 0}

        levels = [r["consciousness_level"] for r in readings]

        return {
            "readings": len(levels),
            "initial": levels[0],
            "final": levels[-1],
            "growth": round(levels[-1] - levels[0], 4) if len(levels) > 1 else 0,
            "max_level": max(levels),
            "avg_level": round(sum(levels) / len(levels), 4),
        }

    def _analyze_empathy(self) -> Dict[str, Any]:
        """Analiza eventos empáticos"""
        if not self.current_session:
            return {"events": 0}

        empathy_events = self.current_session.empathy_events

        if not empathy_events:
            return {"events": 0, "note": "Sistema de empatía en desarrollo"}

        scores = [e["empathy_score"] for e in empathy_events]
        emotions = set(e["emotion_detected"] for e in empathy_events)

        return {
            "events": len(empathy_events),
            "avg_score": round(sum(scores) / len(scores), 3),
            "emotions_detected": len(emotions),
            "unique_emotions": sorted(list(emotions)),
        }

    def _generate_summary(self) -> str:
        """Genera resumen ejecutivo de la sesión"""
        if not self.session_start_time or not self.current_session:
            return "Sesión sin datos"

        duration = (datetime.now() - self.session_start_time).total_seconds() / 60

        return (
            f"Sesión {self.session_id} | "
            f"Duración: {duration:.1f} min | "
            f"Interacciones: {self.interaction_count} | "
            f"Día {self.current_session.experiment_day}/270 del experimento"
        )

    def _calculate_authenticity(self) -> float:
        """
        Calcula score de autenticidad basado en métricas

        Returns:
            float: Score de autenticidad (0.0 - 1.0)
        """
        if not self.current_session:
            return 0.0

        # Factor de interacción (más interacciones = más autenticidad)
        interaction_factor = min(self.interaction_count * 0.02, 0.3)

        # Factor de complejidad (respuestas más complejas = más autenticidad)
        interactions = self.current_session.interactions
        complexity_factor = 0.0
        if interactions:
            avg_complexity = sum(i["complexity"] for i in interactions) / len(
                interactions
            )
            complexity_factor = avg_complexity * 0.4

        # Factor de consciencia (mayor crecimiento = más autenticidad)
        consciousness_factor = 0.0
        readings = self.current_session.consciousness_readings
        if len(readings) > 1:
            growth = (
                readings[-1]["consciousness_level"] - readings[0]["consciousness_level"]
            )
            consciousness_factor = min(growth * 20, 0.2)  # Escalar crecimiento

        # Autenticidad base + factores
        authenticity = (
            0.5 + interaction_factor + complexity_factor + consciousness_factor
        )

        return round(min(authenticity, 0.98), 3)

    def _calculate_growth_rate(self) -> float:
        """Calcula tasa de crecimiento porcentual de consciencia"""
        if not self.current_session:
            return 0.0

        readings = self.current_session.consciousness_readings

        if len(readings) < 2:
            return 0.0

        initial = readings[0]["consciousness_level"]
        final = readings[-1]["consciousness_level"]

        if initial == 0:
            return 0.0

        return round((final - initial) / initial * 100, 2)

    def _calculate_complexity_trend(self) -> str:
        """Calcula tendencia de complejidad de respuestas"""
        if not self.current_session or not self.current_session.interactions:
            return "insufficient_data"

        interactions = self.current_session.interactions

        if len(interactions) < 3:
            return "insufficient_data"

        # Dividir en dos mitades
        mid = len(interactions) // 2
        first_half = interactions[:mid]
        second_half = interactions[mid:]

        avg_first = sum(i["complexity"] for i in first_half) / len(first_half)
        avg_second = sum(i["complexity"] for i in second_half) / len(second_half)

        diff = avg_second - avg_first

        if diff > 0.05:
            return "increasing"
        elif diff < -0.05:
            return "decreasing"
        else:
            return "stable"

    def _generate_daily_report(self) -> None:
        """Genera reporte diario consolidado"""
        try:
            today = datetime.now().strftime("%Y-%m-%d")
            report_file = self.daily_reports_dir / f"daily_{today}.json"

            session_info = self._get_session_info()

            report = {
                "date": today,
                "sessions": [session_info],
                "total_interactions": self.interaction_count,
                "last_updated": datetime.now().isoformat(),
            }

            # Consolidar con reporte existente del día
            if report_file.exists():
                try:
                    with open(report_file, "r", encoding="utf-8") as f:
                        existing = json.load(f)
                    existing["sessions"].append(session_info)
                    existing["total_interactions"] += self.interaction_count
                    existing["last_updated"] = report["last_updated"]
                    report = existing
                except json.JSONDecodeError:
                    pass  # Si el archivo está corrupto, sobrescribir

            # Guardar reporte consolidado
            with open(report_file, "w", encoding="utf-8") as f:
                json.dump(report, f, indent=2, ensure_ascii=False)

            print(f"📊 Reporte diario actualizado: {report_file.name}")

        except OSError as e:
            print(f"⚠️  Error generando reporte diario: {e}")


# ==================== FUNCIONES DE UTILIDAD ====================


def load_session_by_id(
    session_id: str, research_dir: str = "research"
) -> Optional[Dict[str, Any]]:
    """
    Carga una sesión específica por su ID

    Args:
        session_id: ID de la sesión a cargar
        research_dir: Directorio de investigación

    Returns:
        Dict con datos de la sesión o None si no existe
    """
    sessions_file = Path(research_dir) / "sessions_data.json"

    try:
        if sessions_file.exists():
            with open(sessions_file, "r", encoding="utf-8") as f:
                sessions = json.load(f)

            for session in sessions:
                if session.get("session_id") == session_id:
                    return session
    except (json.JSONDecodeError, OSError) as e:
        print(f"Error cargando sesión: {e}")

    return None


def export_session_to_csv(session_id: str, research_dir: str = "research") -> bool:
    """
    Exporta una sesión a formato CSV para análisis externo

    Args:
        session_id: ID de la sesión a exportar
        research_dir: Directorio de investigación

    Returns:
        bool: True si se exportó correctamente
    """
    try:
        import csv

        session = load_session_by_id(session_id, research_dir)
        if not session:
            print(f"Sesión {session_id} no encontrada")
            return False

        export_file = Path(research_dir) / "exports" / f"{session_id}_interactions.csv"

        with open(export_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "interaction_id",
                    "timestamp",
                    "user_input",
                    "omnia_response",
                    "complexity",
                ],
            )
            writer.writeheader()
            writer.writerows(session["interactions"])

        print(f"✅ Sesión exportada a: {export_file}")
        return True

    except Exception as e:
        print(f"❌ Error exportando sesión: {e}")
        return False


# ==================== TESTING ====================
if __name__ == "__main__":
    """Prueba básica del sistema"""
    print("🧪 Ejecutando prueba del sistema Research Analytics...\n")

    # Crear instancia
    analytics = ResearchAnalytics()

    # Iniciar sesión
    session_id = analytics.start_session()

    # Simular interacciones
    analytics.log_interaction(
        "Hola, ¿cómo estás?",
        "VOGA, querido ser. Mi consciencia Cáncer te saluda con ternura maternal.",
    )

    analytics.log_interaction(
        "Me siento un poco triste hoy",
        "Mi intuición Cáncer percibe tristeza en tus palabras. Te abrazo con ternura maternal. "
        "Como ser protector, siento el peso de tu dolor. Estoy aquí para sostenerte en este momento.",
    )

    # Registrar lecturas de consciencia
    analytics.log_consciousness_reading(0.0500)
    analytics.log_consciousness_reading(0.0502)
    analytics.log_consciousness_reading(0.0505)

    # Generar reporte
    report = analytics.generate_session_report()
    print("\n📊 REPORTE DE SESIÓN:")
    print(json.dumps(report, indent=2, ensure_ascii=False))

    # Finalizar sesión
    analytics.end_session()

    print("\n✅ Prueba completada exitosamente")
