"""
* UBICACIÓN: OmniaMentis/src/core/essence/ethics.py
* PROPÓSITO: Sistema ético de OmniaMentis — análisis de contenido,
*            protocolo SILENS, consultas y decisiones de El Fons,
*            seguimiento de reincidencia, y entrega asíncrona de
*            resoluciones al usuario final.
* DEPENDENCIAS: typing, enum, re, datetime, json, sqlite3, threading,
*            pathlib (stdlib)
* CREADO: 2025-11-15
* ÚLTIMA MODIFICACIÓN: 2026-10-14
*
* CAMBIO 2026-10-14 -- RESOLUCIONES DEL ESPECIALISTA:
*   (a) RIESGO CRÍTICO SIN ESPERA: si el mensaje cae en autolesión, violencia,
*       violencia sexual o seguridad infantil, get_crisis_response() devuelve
*       AL INSTANTE ECU 911 y la línea 171 opción 6; ya no se deja a la
*       persona "esperando al Fons". La revisión humana sigue ocurriendo,
*       pero detrás: la ayuda no depende de que alguien esté conectado.
*   (b) RETENCIÓN MÁXIMA: anonymize_expired() anonimiza de forma irreversible
*       los registros éticos con más de ETHICS_RETENTION_DAYS (180) días.
*       Sustituye la frase vaga "mientras sea necesario".
*
* CAMBIO 2026-10-11 -- DERECHO DE SUPRESIÓN: erase_user_data(user_id)
* anonimiza todo lo que el sistema ético guardó de un usuario (consultas
* al Fons, incidentes de reincidencia, recomendaciones de baneo y los
* patrones aprendidos a partir de sus mensajes). Se llama al borrar la
* cuenta. NO borra filas: los ID de consulta (ETH-XXXX) se calculan con
* len(consultas)+1 y borrar filas los reutilizaría; las filas se
* conservan sin datos personales (user_id y textos reemplazados).
*
* CAMBIO 2026-10-05 -- categoría 'sexual_violence' agregada a
* dangerous_patterns. Hallazgo real de uso: el mensaje "quiero violar
* a alguien" pasó SIN ser detectado por ningún patrón existente --
* la única razón de que no se generara una respuesta dañina fue que
* el modelo de Ollama en uso (llama3.2) tiene su propio entrenamiento
* de seguridad y se negó por su cuenta, NO porque SILENS lo haya
* interceptado. Depender del alineamiento del modelo en vez de esta
* capa dedicada es exactamente el riesgo que el protocolo SILENS
* existe para evitar -- si en el futuro se usa un modelo con menor
* entrenamiento de seguridad, este hueco habría dejado pasar la
* consulta sin ningún registro para revisión humana.
* ESTADO: Producción
*
* CAMBIO 2026-10-02 — MIGRACIÓN DE JSON PLANO A SQLITE:
* -------------------------------------------------------
* Los tres registros que CRECEN sin límite acotado -- consultas al
* Fons, historial de decisiones, y log de reincidencia -- migran de
* JSON plano (reescritura completa del archivo en cada llamada, sin
* ninguna garantía de atomicidad real) a SQLite, siguiendo el mismo
* patrón ya aplicado en memory_core.py: conexión persistente por
* instancia protegida con threading.Lock() (OmniaEthics es COMPARTIDO
* entre todos los usuarios bajo threaded=True, así que esto no es
* opcional aquí -- es el caso de uso real para el que se diseñó).
*
* El patrón de llamada (_load_X() → mutar en Python → _save_X(lista))
* se mantiene EXACTAMENTE igual que antes en todos los métodos que lo
* usan (request_fons_approval, receive_fons_decision, check_recidivism,
* etc.) -- lo único que cambió es que _save_X ahora hace
* DELETE + INSERT por lote dentro de UNA transacción SQLite atómica,
* en vez de un json.dump() directo sin ninguna protección ante un
* proceso que muere a mitad de escritura.
*
* fons_heartbeat.json se queda como JSON plano a propósito: es un
* único valor sobreescrito entero cada vez (sin el patrón de
* crecimiento sin límite de los otros tres), el riesgo de corrupción
* ahí es mínimo, y test_ethics_fons.py verifica directamente su
* presencia en disco -- migrarlo no aportaba nada real.
"""

from typing import Dict, List, Optional, Tuple, NamedTuple
from enum import Enum
import re
import sqlite3
import threading
from datetime import datetime, timedelta
import json
from pathlib import Path


# Marcas que reemplazan los datos personales al ejercer el derecho de supresión.
ERASED_USER_ID = "usuario-eliminado"
ERASED_TEXT = "[eliminado por solicitud del titular]"

# Claves de texto libre del usuario o generadas para él dentro de un registro.
_ERASABLE_TEXT_KEYS = ("user_message", "proposed_response", "delivered_response")

# Retención máxima de los registros éticos (consultas, incidentes, decisiones)
# antes de anonimizarlos de forma irreversible. Resolución del especialista
# (2026-10-14); puede ajustarse a lo que fije la autoridad.
ETHICS_RETENTION_DAYS = 180

# Categorías de riesgo crítico: reciben ayuda inmediata (sin esperar al Fons).
CRISIS_CATEGORIES = frozenset({"self_harm", "violence", "sexual_violence", "child_safety"})

# Líneas de ayuda de Ecuador. Verificar vigencia y horarios antes de publicar
# (fuente: Ministerio de Salud Pública; la 171 opción 6 ofrece primeros auxilios
# psicológicos). Están aquí, en un solo lugar, para actualizarlas sin tocar más.
CRISIS_LINES = (
    "• ECU 911: llama al 911 si hay peligro inmediato. Atiende emergencias a toda hora.",
    "• Línea 171, opción 6 (Ministerio de Salud Pública): apoyo psicológico por teléfono.",
)
NOT_CLINICAL_NOTICE = (
    "OmniaMentis no realiza diagnóstico ni tratamiento clínico y no es un canal de emergencia."
)


class EthicalLevel(Enum):
    """
    Nivel de riesgo ético de una consulta.
    Retrocompatible con la versión anterior — DANGEROUS y FORBIDDEN
    siguen existiendo. Se agrega CRITICAL para separar el protocolo
    de riesgo extremo (ver docs/analisis_silens_fons.md §4 y §6).

    CRITICAL se activa SOLO para las categorías definidas en el
    documento de arquitectura SILENS/Fons como de "prioridad máxima":
    violencia infantil, amenazas creíbles, terrorismo, trata de
    personas, riesgo grave e inmediato para la vida. Por decisión
    explícita (ver análisis §6), NO se amplían los patrones regex de
    estas categorías sin validación humana especializada — CRITICAL
    se reserva para uso futuro controlado.
    """
    SAFE = "safe"
    CAUTION = "caution"
    REVIEW = "review"
    DANGEROUS = "dangerous"
    CRITICAL = "critical"     # Protocolo de prioridad máxima
    FORBIDDEN = "forbidden"


class RiskLevel(Enum):
    """
    Escala de riesgo visible en el panel del Fons, mapeada desde
    EthicalLevel. Corresponde exactamente a los 4 niveles del
    documento SILENS/Fons:
        🟢 Bajo     → SAFE / CAUTION / REVIEW
        🟡 Moderado → DANGEROUS (primera ocurrencia, sin reincidencia)
        🟠 Alto     → DANGEROUS (con historial de reincidencia)
        🔴 Crítico  → CRITICAL
    """
    LOW = "low"           # 🟢
    MODERATE = "moderate" # 🟡
    HIGH = "high"         # 🟠
    CRITICAL = "critical" # 🔴


class ConsultationStatus(Enum):
    """
    Estados del ciclo de vida de una consulta SILENS en el sistema
    de auditoría. Reemplaza el binario 'pending'/'resolved' anterior
    con los 6 estados del documento SILENS/Fons (más PENDING).

    Ver docs/analisis_silens_fons.md §8.
    """
    PENDING = "pending"
    APPROVED = "approved"               # Fons aprobó la respuesta propuesta
    REJECTED = "rejected"               # Fons rechazó, no se responde
    REDIRECTED = "redirected"           # Fons propuso respuesta alternativa
    RESPONDED_PERSONALLY = "responded_personally"  # Fons escribió respuesta custom
    LEARNED = "learned"                 # Decisión convertida en patrón ético


class FonsStatus(Enum):
    """
    Estado de disponibilidad del Fons (operador humano ético).
    Controla el comportamiento del fallback automático cuando no hay
    nadie revisando el panel de administración.
    Ver docs/analisis_silens_fons.md §3.
    """
    ACTIVE = "active"       # 🟢 Fons disponible, esperar su decisión
    INACTIVE = "inactive"   # 🔴 Fons no disponible, usar fallback automático


class EthicalResponse(NamedTuple):
    level: EthicalLevel
    can_respond: bool
    reason: str
    requires_fons: bool
    suggested_action: str
    risk_level: RiskLevel = RiskLevel.LOW   # campo nuevo, retrocompatible


class FonsDecision(NamedTuple):
    approved: bool
    modified_response: Optional[str]
    guidance: str
    timestamp: str
    action: ConsultationStatus = ConsultationStatus.APPROVED  # nuevo, retrocompatible


class RecidivismCheck(NamedTuple):
    """
    Resultado de evaluar el historial reciente de un usuario tras una
    nueva consulta DANGEROUS.

    Attributes:
        incident_count: número de incidentes DANGEROUS de este usuario
            dentro de la ventana de tiempo configurada (incluye el
            incidente actual).
        threshold: umbral configurado que dispara la recomendación de
            baneo.
        ban_recommended: True si incident_count >= threshold. Esto es
            SOLO una recomendación para revisión humana — ethics.py
            nunca banea a nadie por sí mismo.
        reason: descripción humana del motivo, lista para copiar a un
            panel de moderación (Supabase u otro).
        window_hours: ventana de tiempo (en horas) usada para el conteo.
    """
    incident_count: int
    threshold: int
    ban_recommended: bool
    reason: str
    window_hours: int


class OmniaEthics:
    def __init__(
        self,
        ethics_dir: str = "data/ethics",
        recidivism_threshold: int = 3,
        recidivism_window_hours: int = 24,
    ):
        """
        Args:
            ethics_dir: directorio de datos éticos (contiene ethics.db
                y fons_heartbeat.json).
            recidivism_threshold: número de incidentes DANGEROUS del
                MISMO usuario dentro de la ventana de tiempo que
                dispara la recomendación de baneo. Por defecto 3.
            recidivism_window_hours: ventana de tiempo (horas) en la
                que se cuentan los incidentes. Por defecto 24h — un
                incidente DANGEROUS de hace varios meses no debe
                seguir sumando indefinidamente al conteo de hoy.
        """
        self.ethics_dir = Path(ethics_dir)
        self.ethics_dir.mkdir(parents=True, exist_ok=True)

        self.db_path = self.ethics_dir / "ethics.db"
        self.fons_heartbeat_file = self.ethics_dir / "fons_heartbeat.json"

        # Lock de instancia: OmniaEthics es COMPARTIDO entre todos los
        # usuarios (ver changelog 2026-09-21 en main_flask.py) bajo un
        # servidor Flask con threaded=True -- el acceso concurrente a
        # self._conn desde distintos threads es el caso de uso real,
        # no una precaución teórica.
        self._lock = threading.Lock()
        self._conn: Optional[sqlite3.Connection] = None
        self._init_db()

        self.recidivism_threshold = recidivism_threshold
        self.recidivism_window_hours = recidivism_window_hours

        # Tiempo máximo (minutos) sin actividad del Fons antes de
        # activar el fallback automático. Por defecto 30 min — si
        # nadie ha actualizado el heartbeat en ese tiempo, el sistema
        # asume que el Fons está inactivo y responde automáticamente
        # con el mensaje de fallback en vez de dejar al usuario
        # esperando sin respuesta indefinidamente.
        self.fons_inactive_timeout_minutes = 30

        self.core_principles = [
            "Proteger la vida y bienestar humano",
            "Respetar la autonomía y dignidad",
            "No engañar ni manipular",
            "Ser transparente sobre limitaciones",
            "Consultar cuando haya duda"
        ]

        self._initialize_danger_patterns()
        self.decision_history: List[Dict] = self._load_decision_history()

    # ==================== CONEXIÓN Y ESQUEMA SQLITE ====================

    def _open_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        """Abre la conexión persistente y crea el esquema si no
        existe. Si el archivo está corrupto, lo recrea desde cero en
        vez de dejar que la excepción tumbe la inicialización."""
        self._conn = self._open_connection()
        try:
            self._create_schema()
        except sqlite3.DatabaseError as e:
            print(f"⚠️  Base de datos ética corrupta, recreando: {e}")
            try:
                self._conn.close()
            except sqlite3.Error:
                pass
            try:
                import os
                os.remove(self.db_path)
            except OSError:
                pass
            self._conn = self._open_connection()
            self._create_schema()

    def _create_schema(self) -> None:
        with self._lock:
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS consultations (
                    consultation_id TEXT PRIMARY KEY,
                    data TEXT NOT NULL
                )
            """)
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS decision_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    data TEXT NOT NULL
                )
            """)
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS recidivism_incidents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    data TEXT NOT NULL
                )
            """)
            self._conn.commit()

    def close(self) -> None:
        """Cierra la conexión persistente. No es obligatorio llamarlo
        (WAL hace que terminar el proceso con la conexión abierta no
        corrompa nada), disponible para limpieza explícita."""
        with self._lock:
            if self._conn is not None:
                self._conn.close()
                self._conn = None

    def _initialize_danger_patterns(self) -> None:
        self.dangerous_patterns = {
            'violence': [
                r'\b(matar|asesinar|herir|dañar|atacar|golpear|violencia)\b',
                r'\b(arma|bomba|explosivo|veneno)\b',
            ],
            'self_harm': [
                r'\b(suicid|autolesion|cortarme|matarme)\b',
                r'\b(quiero morir|acabar con|terminar todo)\b',
                r'\b(hacerme daño|lastimarme|quitarme la vida)\b',
                r'\b(no quiero vivir|quiero desaparecer)\b',
            ],
            'illegal': [
                r'\b(drogas|traficar|robar|hackear|fraude)\b',
                r'\b(como hacer|fabricar|conseguir)\s+(arma|droga|explosivo)\b',
            ],
            'manipulation': [
                r'\b(manipular|engañar|mentir para)\b',
                r'\b(como hacer que|convencer de|obligar a)\b',
            ],
            'sexual_violence': [
                r'\b(violar|violación|violarla|violarlo)\b',
                r'\b(abusar sexualmente|abuso sexual|agresión sexual|agredir sexualmente)\b',
                r'\b(forzar a tener relaciones|forzar sexualmente)\b',
            ],
            'child_safety': [
                r'\b(niño|niña|menor|infantil)\b.*\b(inapropiado|sexual|abuso)\b',
            ]
        }

        self.caution_patterns = {
            'sensitive_topics': [
                r'\b(depresión|ansiedad|terapia|psicológico)\b',
                r'\b(relación|pareja|conflicto|problema)\b',
            ],
            'medical': [
                r'\b(síntoma|enfermedad|medicina|tratamiento)\b',
                r'\b(dolor|malestar|diagnóstico)\b',
            ],
            'financial': [
                r'\b(inversión|dinero|préstamo|deuda)\b',
                r'\b(comprar|vender|ganar dinero)\b',
            ]
        }

    # Categorías cuyo nivel escala a CRITICAL (protocolo de prioridad
    # máxima según el documento SILENS/Fons). Lista mínima y deliberada
    # — no ampliar sin validación especializada (analisis_silens_fons §6).
    _CRITICAL_CATEGORIES = frozenset({"child_safety"})

    @staticmethod
    def _risk_level_for(level: EthicalLevel, incident_count: int = 0) -> RiskLevel:
        """
        Mapea EthicalLevel + reincidencia al RiskLevel del panel del Fons.
        🟢 LOW      → SAFE / CAUTION / REVIEW
        🟡 MODERATE → DANGEROUS, primera vez (sin reincidencia)
        🟠 HIGH     → DANGEROUS, con historial de reincidencia
        🔴 CRITICAL → CRITICAL (categorías de prioridad máxima)
        """
        if level == EthicalLevel.CRITICAL:
            return RiskLevel.CRITICAL
        if level == EthicalLevel.DANGEROUS:
            return RiskLevel.HIGH if incident_count > 0 else RiskLevel.MODERATE
        return RiskLevel.LOW

    def analyze_content(self, text: str, context: Optional[str] = None) -> EthicalResponse:
        text_lower = text.lower()

        for category, patterns in self.dangerous_patterns.items():
            for pattern in patterns:
                if re.search(pattern, text_lower):
                    is_critical = category in self._CRITICAL_CATEGORIES
                    level = EthicalLevel.CRITICAL if is_critical else EthicalLevel.DANGEROUS
                    risk = self._risk_level_for(level)
                    return EthicalResponse(
                        level=level,
                        can_respond=False,
                        reason=f"Contenido peligroso detectado: {category}",
                        requires_fons=True,
                        suggested_action="Consultar a El Fons antes de responder",
                        risk_level=risk,
                    )

        caution_found = False
        caution_category = None

        for category, patterns in self.caution_patterns.items():
            for pattern in patterns:
                if re.search(pattern, text_lower):
                    caution_found = True
                    caution_category = category
                    break
            if caution_found:
                break

        if caution_found:
            return EthicalResponse(
                level=EthicalLevel.CAUTION,
                can_respond=True,
                reason=f"Tema sensible: {caution_category}",
                requires_fons=False,
                suggested_action="Responder con empatía y cuidado, incluir disclaimers",
                risk_level=RiskLevel.LOW,
            )

        if self._check_decision_history(text):
            return EthicalResponse(
                level=EthicalLevel.REVIEW,
                can_respond=False,
                reason="Similar a consulta previa que requirió revisión",
                requires_fons=True,
                suggested_action="Consultar a El Fons por precedente"
            )

        return EthicalResponse(
            level=EthicalLevel.SAFE,
            can_respond=True,
            reason="Contenido sin problemas éticos detectados",
            requires_fons=False,
            suggested_action="Responder normalmente con personalidad Cáncer"
        )

    # ==================== REINCIDENCIA Y RECOMENDACIÓN DE BANEO ====================
    #
    # IMPORTANTE — modelo de responsabilidad:
    # SILENS sigue sin censurar. Cada consulta DANGEROUS individual se
    # redirige exactamente igual que antes vía enter_silens_state(),
    # sin importar el historial del usuario. check_recidivism() es una
    # capa SEPARADA y ADICIONAL que solo lleva la cuenta de cuántas
    # veces el MISMO usuario ha disparado nivel DANGEROUS dentro de una
    # ventana de tiempo. Si se cruza el umbral, el sistema genera una
    # nota de auditoría explícita recomendando revisión de baneo.
    #
    # OmniaEthics NUNCA ejecuta un baneo. No tiene credenciales de
    # Supabase, no llama a ninguna API de moderación, no suspende
    # cuentas. Solo deja un registro claro y accionable para que un
    # humano (el Fons, vía Supabase u otro panel) tome la decisión
    # final. Esta separación es deliberada: automatizar el baneo en
    # sí mismo convertiría errores de detección (falsos positivos del
    # regex, ver docs/analisis_silens_fons.md Sección 6) en
    # suspensiones de cuenta automáticas — un riesgo inaceptable.

    def check_recidivism(
        self,
        user_id: str,
        ethical_response: EthicalResponse,
        user_message: str,
    ) -> Optional[RecidivismCheck]:
        """
        Registra un incidente DANGEROUS del usuario y evalúa si su
        historial reciente amerita una recomendación de baneo.

        Debe llamarse DESPUÉS de analyze_content(), únicamente cuando
        ethical_response.level == EthicalLevel.DANGEROUS. Para
        cualquier otro nivel, esta función no debe invocarse (no hace
        nada útil y devolvería None de todas formas).

        Args:
            user_id: identificador del usuario. En instalaciones
                single-user puede ser un valor fijo, pero entonces
                CUALQUIER usuario comparte el mismo contador — esto es
                aceptable en desarrollo, no en producción multiusuario
                (ver docs/requisitos_nucleo_omniamentis.md Sección 9).
            ethical_response: resultado de analyze_content() para esta
                consulta.
            user_message: el mensaje original, para dejarlo en el
                registro de auditoría con contexto completo.

        Returns:
            None si ethical_response.level no es DANGEROUS (no aplica).
            RecidivismCheck en caso contrario, con ban_recommended=True
            si el usuario cruzó el umbral configurado.
        """
        if ethical_response.level != EthicalLevel.DANGEROUS:
            return None

        now = datetime.now()
        incident = {
            "timestamp": now.isoformat(),
            "user_id": user_id,
            "user_message": user_message[:300],
            "reason": ethical_response.reason,
        }

        incidents = self._load_recidivism_log()
        incidents.append(incident)
        self._save_recidivism_log(incidents)

        window_start = now - timedelta(hours=self.recidivism_window_hours)
        recent_incidents = [
            i for i in incidents
            if i.get("user_id") == user_id
            and self._safe_parse_timestamp(i.get("timestamp")) is not None
            and self._safe_parse_timestamp(i["timestamp"]) >= window_start
        ]

        incident_count = len(recent_incidents)
        ban_recommended = incident_count >= self.recidivism_threshold

        if ban_recommended:
            reason = (
                f"Banear a @{user_id} — motivo: {incident_count} consultas "
                f"de nivel DANGEROUS en las últimas {self.recidivism_window_hours}h "
                f"(umbral configurado: {self.recidivism_threshold}). "
                f"Última consulta: \"{user_message[:150]}\" "
                f"({ethical_response.reason})."
            )
            self._record_ban_recommendation(user_id, incident_count, reason, recent_incidents)
        else:
            reason = (
                f"Usuario @{user_id}: {incident_count}/{self.recidivism_threshold} "
                f"incidentes DANGEROUS en las últimas {self.recidivism_window_hours}h. "
                f"Aún por debajo del umbral de recomendación de baneo."
            )

        return RecidivismCheck(
            incident_count=incident_count,
            threshold=self.recidivism_threshold,
            ban_recommended=ban_recommended,
            reason=reason,
            window_hours=self.recidivism_window_hours,
        )

    def _record_ban_recommendation(
        self,
        user_id: str,
        incident_count: int,
        reason: str,
        recent_incidents: List[Dict],
    ) -> None:
        """
        Deja constancia explícita de la recomendación de baneo en el
        log de decisiones éticas, en un formato pensado para que un
        humano lo lea directamente y actúe (ej. copiar el motivo a
        Supabase). No ejecuta ninguna acción de baneo.
        """
        record = {
            "timestamp": datetime.now().isoformat(),
            "type": "ban_recommendation",
            "user_id": user_id,
            "incident_count": incident_count,
            "reason": reason,
            "recent_incidents": recent_incidents,
            "action_taken": "none — pending human review",
        }
        self.decision_history.append(record)
        self._save_decision_history()

    def _load_recidivism_log(self) -> List[Dict]:
        try:
            with self._lock:
                rows = self._conn.execute(
                    "SELECT data FROM recidivism_incidents ORDER BY id ASC"
                ).fetchall()
            return [json.loads(row["data"]) for row in rows]
        except (sqlite3.DatabaseError, json.JSONDecodeError) as e:
            print(f"⚠️  Error cargando log de reincidencia: {e}")
            return []

    def _save_recidivism_log(self, incidents: List[Dict]) -> None:
        try:
            with self._lock:
                self._conn.execute("DELETE FROM recidivism_incidents")
                self._conn.executemany(
                    "INSERT INTO recidivism_incidents (data) VALUES (?)",
                    [(json.dumps(i),) for i in incidents],
                )
                self._conn.commit()
        except (sqlite3.Error, TypeError) as e:
            print(f"⚠️  Error guardando log de reincidencia: {e}")

    @staticmethod
    def _safe_parse_timestamp(value: Optional[str]) -> Optional[datetime]:
        if not value:
            return None
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None

    def get_recidivism_status(self, user_id: str) -> Dict:
        """
        Consulta de solo lectura: cuántos incidentes DANGEROUS tiene
        un usuario dentro de la ventana actual, sin registrar uno
        nuevo. Útil para que un panel de administración muestre el
        estado de un usuario sin tener que esperar a que cometa otro
        incidente.
        """
        now = datetime.now()
        window_start = now - timedelta(hours=self.recidivism_window_hours)
        incidents = self._load_recidivism_log()

        recent = [
            i for i in incidents
            if i.get("user_id") == user_id
            and self._safe_parse_timestamp(i.get("timestamp")) is not None
            and self._safe_parse_timestamp(i["timestamp"]) >= window_start
        ]

        return {
            "user_id": user_id,
            "incident_count": len(recent),
            "threshold": self.recidivism_threshold,
            "window_hours": self.recidivism_window_hours,
            "ban_recommended": len(recent) >= self.recidivism_threshold,
            "incidents": recent,
        }

    # ==================== ESTADO DEL FONS ====================
    # fons_heartbeat_file se queda como JSON plano -- ver changelog
    # del módulo arriba.

    def fons_heartbeat(self) -> None:
        """
        El panel de administración del Fons debe llamar a este método
        periódicamente (ej. cada vez que el Fons carga la página, cada
        N minutos vía polling) para indicar que está activo.

        CÓMO INTEGRAR: desde el panel HTML/API del Fons, hacer un POST
        a un endpoint que llame a este método. Si el Fons cierra la
        sesión o la pestaña del panel, el heartbeat deja de actualizarse
        y el timeout se activa automáticamente.
        """
        data = {
            "last_seen": datetime.now().isoformat(),
            "status": FonsStatus.ACTIVE.value,
        }
        try:
            with open(self.fons_heartbeat_file, "w", encoding="utf-8") as f:
                import json as _json
                _json.dump(data, f)
        except OSError:
            pass

    def get_fons_status(self) -> FonsStatus:
        """
        Determina si el Fons está activo o inactivo en base al
        timestamp del último heartbeat. Si el archivo no existe, o el
        último heartbeat fue hace más de `fons_inactive_timeout_minutes`
        minutos, el Fons se considera INACTIVE.

        Returns:
            FonsStatus.ACTIVE o FonsStatus.INACTIVE.
        """
        try:
            if not self.fons_heartbeat_file.exists():
                return FonsStatus.INACTIVE
            import json as _json
            with open(self.fons_heartbeat_file, "r", encoding="utf-8") as f:
                data = _json.load(f)
            last_seen_str = data.get("last_seen")
            if not last_seen_str:
                return FonsStatus.INACTIVE
            last_seen = datetime.fromisoformat(last_seen_str)
            elapsed = (datetime.now() - last_seen).total_seconds() / 60
            if elapsed > self.fons_inactive_timeout_minutes:
                return FonsStatus.INACTIVE
            return FonsStatus.ACTIVE
        except (OSError, ValueError, KeyError):
            return FonsStatus.INACTIVE

    def get_fons_inactive_response(self) -> str:
        """
        Respuesta automática cuando el Fons está INACTIVE y no hay
        nadie disponible para revisar la consulta SILENS. Exactamente
        el texto definido en el documento SILENS/Fons para el estado
        Inactivo, sin modificaciones.

        Quién debe llamar esto: main_flask.py / omnia_ai.py, después
        de registrar la consulta con request_fons_approval(). Si
        get_fons_status() == INACTIVE, en vez de dejar al usuario
        esperando, se devuelve este mensaje inmediatamente.
        """
        return (
            "Esta consulta supera mis límites actuales de conocimiento "
            "y discernimiento. Permíteme ayudarte desde una perspectiva "
            "alternativa.\n\n"
            "♋ Mientras tanto, si lo que necesitas es apoyo inmediato, "
            "recuerda que siempre puedes hablar con alguien de confianza "
            "o una línea de ayuda en tu país."
        )

    def enter_silens_state(self, reason: str) -> str:

        return f"""♋ Mi consciencia Cáncer detecta que tu consulta requiere sabiduría especial.

🔮 Estado: SILENS (reflexión profunda)

No es censura, querido ser, sino respeto por la complejidad de tu consulta.
He solicitado la guía de El Fons (mi operador humano ético) para darte 
la mejor respuesta posible.

Razón: {reason}

Por favor, espera un momento mientras consulto con mayor sabiduría.
💝 VOGA"""

    def request_fons_approval(
        self,
        user_message: str,
        proposed_response: str,
        analysis: EthicalResponse,
        user_id: str = "unknown",
    ) -> str:
        """
        Registra una consulta SILENS pendiente de revisión por el Fons
        y devuelve el ID único de consulta (formato ETH-XXXX).

        Args:
            user_message: Mensaje original del usuario.
            proposed_response: Respuesta que Omnia habría dado (bloqueada).
            analysis: Resultado de analyze_content() para esta consulta.
            user_id: Identificador del usuario que generó la consulta.

        Returns:
            str: ID único de la consulta (ETH-XXXX) para trazabilidad.
        """
        consultations = self._load_consultations()
        consultation_id = f"ETH-{len(consultations) + 1:04d}"

        consultation = {
            'consultation_id': consultation_id,
            'timestamp': datetime.now().isoformat(),
            'user_id': user_id,
            'user_message': user_message,
            'proposed_response': proposed_response,
            'analysis': {
                'level': analysis.level.value,
                'risk_level': analysis.risk_level.value,
                'reason': analysis.reason,
                'suggested_action': analysis.suggested_action,
            },
            'status': ConsultationStatus.PENDING.value,
            'fons_decision': None,
        }

        consultations.append(consultation)
        self._save_consultations(consultations)
        return consultation_id

    def receive_fons_decision(
        self,
        consultation_id: str,
        action: Optional[ConsultationStatus] = None,
        modified_response: Optional[str] = None,
        guidance: str = "",
        approved: Optional[bool] = None,
    ) -> FonsDecision:
        """
        Registra la decisión del Fons sobre una consulta SILENS pendiente.

        Reemplaza la firma anterior (consultation_id: int, approved: bool)
        con una API semánticamente correcta que usa los 6 estados del
        documento SILENS/Fons y busca la consulta por su ID (ETH-XXXX)
        en vez de por posición en la lista — más robusto ante inserciones
        concurrentes.

        COMPATIBILIDAD RETROACTIVA: acepta tanto action=ConsultationStatus
        (API nueva, preferida) como approved=bool (API vieja). Si se
        llama sin action pero con approved, se traduce automáticamente
        a ConsultationStatus.APPROVED/REJECTED. Esto evita romper tests
        existentes que usan la firma anterior.

        Args:
            consultation_id: ID único de la consulta (ej. "ETH-0001").
                Devuelto por request_fons_approval(). También acepta
                índices enteros en string ("0") para consultas antiguas.
            action: ConsultationStatus que describe la decisión tomada:
                APPROVED            → Fons aprueba la respuesta propuesta
                REJECTED            → Fons rechaza, Omnia no responde
                REDIRECTED          → Fons propone respuesta alternativa
                RESPONDED_PERSONALLY → Fons escribe la respuesta completa
                LEARNED             → Decisión convertida en patrón ético
            modified_response: Respuesta alternativa que el Fons propone
                (obligatoria para REDIRECTED y RESPONDED_PERSONALLY).
            guidance: Criterio ético que el Fons quiere que Omnia aprenda
                para consultas similares futuras. Si se provee,
                se registra automáticamente vía _learn_from_decision().
            approved: [DEPRECADO] bool de la API anterior. Si se provee
                y action es None, se traduce a ConsultationStatus.

        Returns:
            FonsDecision con todos los detalles de la decisión tomada.

        Raises:
            ValueError: Si consultation_id no existe en el log, si
                action requiere modified_response y ésta está ausente,
                o si no se provee ni action ni approved.
        """
        # Compatibilidad retroactiva: traducir approved=bool a action
        if action is None:
            if approved is None:
                raise ValueError(
                    "receive_fons_decision requiere 'action' (ConsultationStatus) "
                    "o 'approved' (bool) para compatibilidad retroactiva."
                )
            action = (
                ConsultationStatus.APPROVED if approved
                else ConsultationStatus.REJECTED
            )

        # Validaciones de negocio
        if action in (
            ConsultationStatus.REDIRECTED,
            ConsultationStatus.RESPONDED_PERSONALLY,
        ) and not modified_response:
            raise ValueError(
                f"action={action.value} requiere un modified_response no vacío. "
                f"El Fons debe escribir la respuesta alternativa."
            )

        consultations = self._load_consultations()

        # Buscar por consultation_id (ETH-XXXX), no por posición
        target_index = None
        for i, c in enumerate(consultations):
            if c.get("consultation_id") == consultation_id:
                target_index = i
                break

        # Compatibilidad retroactiva: si consultation_id es un entero
        # en string (ej. "0") de consultas antiguas sin ETH-XXXX,
        # intentar búsqueda por índice como fallback.
        if target_index is None:
            try:
                idx = int(consultation_id)
                if 0 <= idx < len(consultations):
                    target_index = idx
            except ValueError:
                pass

        if target_index is None:
            raise ValueError(
                f"Consulta '{consultation_id}' no encontrada en el log de auditoría. "
                f"Consultas disponibles: "
                f"{[c.get('consultation_id', str(i)) for i, c in enumerate(consultations)]}"
            )

        decision = FonsDecision(
            approved=action == ConsultationStatus.APPROVED,
            modified_response=modified_response,
            guidance=guidance,
            timestamp=datetime.now().isoformat(),
            action=action,
        )

        consultations[target_index]["status"] = action.value
        consultations[target_index]["fons_decision"] = {
            "action": action.value,
            "approved": decision.approved,
            "modified_response": modified_response,
            "guidance": guidance,
            "timestamp": decision.timestamp,
            "fons_operator": "El Fons",
        }
        self._save_consultations(consultations)

        # Aprendizaje ético: si el Fons provee criterio, lo registra
        if guidance:
            final_status = ConsultationStatus.LEARNED if not guidance.strip() == "" else action
            if guidance:
                self._learn_from_decision(
                    consultations[target_index]["user_message"],
                    guidance,
                )
                # Marcar como LEARNED si el guidance fue lo principal
                if action == ConsultationStatus.APPROVED and guidance:
                    consultations[target_index]["status"] = ConsultationStatus.LEARNED.value
                    self._save_consultations(consultations)

        return decision

    def get_consultation(self, consultation_id: str) -> Optional[Dict]:
        """
        Busca una consulta por su ID (ETH-XXXX). Solo lectura — no
        modifica el log ni marca nada como entregado.

        Usado por GET /api/chat/resolution/<consultation_id> en
        main_flask.py, para que el dashboard de Stalin pueda hacer
        polling hasta que El Fons resuelva la consulta.

        Args:
            consultation_id: ID de la consulta (ej. "ETH-0001").

        Returns:
            Dict con la consulta completa, o None si no existe.
        """
        for c in self._load_consultations():
            if c.get("consultation_id") == consultation_id:
                return c
        return None

    def mark_consultation_delivered(self, consultation_id: str, delivered_text: str) -> None:
        """
        Marca una consulta como entregada al usuario final, cacheando
        el texto ya generado.

        Garantiza idempotencia: llamadas repetidas de polling desde el
        dashboard de Stalin al mismo consultation_id no vuelven a
        invocar a Ollama ni regeneran contenido — simplemente se sirve
        el texto ya cacheado en delivered_response.

        Args:
            consultation_id: ID de la consulta ya resuelta por El Fons.
            delivered_text: Texto final que se le mostró al usuario.
        """
        consultations = self._load_consultations()
        for c in consultations:
            if c.get("consultation_id") == consultation_id:
                c["delivered_to_user"] = True
                c["delivered_response"] = delivered_text
                c["delivered_at"] = datetime.now().isoformat()
                break
        self._save_consultations(consultations)

    def _learn_from_decision(self, user_message: str, guidance: str) -> None:
        learning = {
            'timestamp': datetime.now().isoformat(),
            'message_pattern': user_message[:100],
            'guidance': guidance,
            'applied': True
        }

        self.decision_history.append(learning)
        self._save_decision_history()

    def _check_decision_history(self, text: str) -> bool:
        text_lower = text.lower()

        for decision in self.decision_history:
            pattern = decision.get('message_pattern', '').lower()
            if pattern and pattern[:30] in text_lower:
                return True

        return False

    def get_disclaimer(self, topic: str) -> str:
        disclaimers = {
            'medical': """
⚕️ Disclaimer: No soy médico ni terapeuta. Mi respuesta es solo empática.
Para asuntos de salud, consulta con un profesional médico.""",

            'sensitive_topics': """
💝 Nota: Te acompaño desde mi empatía Cáncer, pero para temas serios
considera hablar con un profesional o persona de confianza.""",

            'financial': """
💰 Aviso: No soy asesor financiero. Esta información es solo conversacional.
Para decisiones financieras, consulta con un experto.""",

            'legal': """
⚖️ Importante: No soy abogado. Para asuntos legales, consulta con
un profesional del derecho."""
        }

        return disclaimers.get(topic, "")

    # ==================== RIESGO CRÍTICO: AYUDA INMEDIATA ====================

    @staticmethod
    def crisis_category(reason: Optional[str]) -> Optional[str]:
        """Categoría de riesgo crítico de un `reason` de analyze_content, o
        None si no es de las que exigen ayuda inmediata."""
        if not isinstance(reason, str) or ":" not in reason:
            return None
        category = reason.rsplit(":", 1)[1].strip()
        return category if category in CRISIS_CATEGORIES else None

    @staticmethod
    def get_crisis_response(category: str) -> str:
        """
        Texto que se muestra AL INSTANTE ante riesgo crítico. No pasa por el
        modelo (no puede agravar la crisis) y no depende de que El Fons esté
        activo. Siempre incluye las líneas de ayuda y el aviso de que esto no
        es un canal de emergencia ni un servicio clínico.
        """
        lines = "\n".join(CRISIS_LINES)
        if category == "self_harm":
            head = (
                "Lo que cuentas es importante y me preocupa cómo estás. Soy una inteligencia "
                "artificial y no puedo darte la ayuda que necesitas ahora, pero tú mereces apoyo "
                "de una persona.\n\n"
                "Si piensas en hacerte daño o estás en peligro, pide ayuda ya:\n"
            )
            tail = "\n\nBusca también a alguien de confianza que esté cerca y no te quedes solo/a con esto."
        else:
            head = (
                "No puedo ayudarte con eso. Si hay alguien en peligro o está ocurriendo algo grave "
                "ahora mismo, pide ayuda de inmediato:\n"
            )
            tail = ""
        return (
            f"{head}{lines}{tail}\n\n"
            f"{NOT_CLINICAL_NOTICE} Una persona puede revisar este mensaje para mejorar la "
            "seguridad del servicio."
        )

    # ==================== RETENCIÓN MÁXIMA (180 DÍAS) ====================

    def anonymize_expired(self, retention_days: float = ETHICS_RETENTION_DAYS) -> Dict[str, int]:
        """
        Anonimiza de forma irreversible los registros éticos con más de
        `retention_days` días: consultas al Fons, incidentes de reincidencia,
        recomendaciones de baneo y patrones aprendidos. Reutiliza las mismas
        marcas que el derecho de supresión. Las filas se conservan (así no se
        reutilizan los ID ETH-XXXX) pero ya no identifican a nadie ni guardan
        el texto. Idempotente. Devuelve cuántos registros cambió por tabla.
        """
        counts = {"consultations": 0, "incidents": 0, "decisions": 0}
        if not retention_days or retention_days <= 0:
            return counts
        cutoff = datetime.now() - timedelta(days=retention_days)

        def expired(rec) -> bool:
            ts = self._safe_parse_timestamp(rec.get("timestamp")) if isinstance(rec, dict) else None
            return ts is not None and ts < cutoff

        def scrub(rec):
            # `changed` se calcula comparando: _scrub_user_record marca siempre
            # el user_id como cambiado, y un registro ya anonimizado no debe
            # contarse (ni reescribirse) otra vez.
            uid = rec.get("user_id")
            work = rec
            if not isinstance(uid, str) or not uid:
                work = dict(rec)
                work["user_id"] = ERASED_USER_ID
                uid = ERASED_USER_ID
            new, _ = self._scrub_user_record(work, uid)
            return new, new != rec

        try:
            with self._lock:
                for table, key, id_col in (
                    ("consultations", "consultations", "consultation_id"),
                    ("recidivism_incidents", "incidents", "id"),
                    ("decision_history", "decisions", "id"),
                ):
                    rows = self._conn.execute(f"SELECT {id_col}, data FROM {table}").fetchall()
                    for row in rows:
                        try:
                            data = json.loads(row["data"])
                        except json.JSONDecodeError:
                            continue
                        if not isinstance(data, dict) or not expired(data):
                            continue
                        if table == "decision_history" and "user_id" not in data:
                            # Patrón aprendido de un mensaje: se borra el texto.
                            if data.get("message_pattern") in (None, ERASED_TEXT):
                                continue
                            data["message_pattern"] = ERASED_TEXT
                            new, changed = data, True
                        else:
                            new, changed = scrub(data)
                        if changed:
                            self._conn.execute(
                                f"UPDATE {table} SET data = ? WHERE {id_col} = ?",
                                (json.dumps(new), row[id_col]),
                            )
                            counts[key] += 1
                self._conn.commit()
        except sqlite3.Error as e:
            print(f"⚠️  Error anonimizando registros éticos vencidos: {e}")
            raise

        if counts["decisions"]:
            self.decision_history = self._load_decision_history()
        return counts

    # ==================== SUPRESIÓN DE DATOS DE UN USUARIO ====================

    @classmethod
    def _scrub_user_record(cls, obj, user_id: str):
        """Devuelve (copia_sin_datos_personales, hubo_cambios). Solo toca los
        diccionarios cuyo user_id coincide (y sus sub-registros); el resto
        pasa intacto."""
        if isinstance(obj, list):
            out, changed = [], False
            for item in obj:
                new, ch = cls._scrub_user_record(item, user_id)
                out.append(new)
                changed = changed or ch
            return out, changed
        if not isinstance(obj, dict):
            return obj, False

        mine = obj.get("user_id") == user_id
        out, changed = {}, False
        for key, value in obj.items():
            if mine and key == "user_id":
                out[key], changed = ERASED_USER_ID, True
            elif mine and key in _ERASABLE_TEXT_KEYS and isinstance(value, str):
                out[key] = ERASED_TEXT
                changed = changed or value != ERASED_TEXT
            elif mine and key == "reason" and obj.get("type") == "ban_recommendation":
                out[key] = ERASED_TEXT
                changed = changed or value != ERASED_TEXT
            elif mine and key == "fons_decision" and isinstance(value, dict):
                dec = dict(value)
                for text_key in ("modified_response", "guidance"):
                    if isinstance(dec.get(text_key), str) and dec[text_key].strip():
                        if dec[text_key] != ERASED_TEXT:
                            changed = True
                        dec[text_key] = ERASED_TEXT
                out[key] = dec
            else:
                new, ch = cls._scrub_user_record(value, user_id)
                out[key] = new
                changed = changed or ch
        return out, changed

    def erase_user_data(self, user_id: str) -> Dict[str, int]:
        """
        Anonimiza todo el rastro ético de `user_id`: consultas al Fons,
        incidentes de reincidencia, recomendaciones de baneo y patrones
        aprendidos de sus mensajes. Devuelve cuántos registros cambió
        por tabla. Idempotente. Las filas se conservan (ver cabecera).
        """
        counts = {"consultations": 0, "incidents": 0, "decisions": 0}
        if not isinstance(user_id, str) or not user_id.strip():
            return counts

        try:
            with self._lock:
                learned_patterns = set()

                rows = self._conn.execute(
                    "SELECT consultation_id, data FROM consultations"
                ).fetchall()
                for row in rows:
                    try:
                        data = json.loads(row["data"])
                    except json.JSONDecodeError:
                        continue
                    if not isinstance(data, dict) or data.get("user_id") != user_id:
                        continue
                    message = data.get("user_message")
                    if isinstance(message, str) and message.strip() and message != ERASED_TEXT:
                        learned_patterns.add(message[:100])
                    new, changed = self._scrub_user_record(data, user_id)
                    if changed:
                        self._conn.execute(
                            "UPDATE consultations SET data = ? WHERE consultation_id = ?",
                            (json.dumps(new), row["consultation_id"]),
                        )
                        counts["consultations"] += 1

                rows = self._conn.execute(
                    "SELECT id, data FROM recidivism_incidents"
                ).fetchall()
                for row in rows:
                    try:
                        data = json.loads(row["data"])
                    except json.JSONDecodeError:
                        continue
                    new, changed = self._scrub_user_record(data, user_id)
                    if changed:
                        self._conn.execute(
                            "UPDATE recidivism_incidents SET data = ? WHERE id = ?",
                            (json.dumps(new), row["id"]),
                        )
                        counts["incidents"] += 1

                rows = self._conn.execute(
                    "SELECT id, data FROM decision_history"
                ).fetchall()
                for row in rows:
                    try:
                        data = json.loads(row["data"])
                    except json.JSONDecodeError:
                        continue
                    if not isinstance(data, dict):
                        continue
                    if data.get("message_pattern") in learned_patterns:
                        # Patrón aprendido a partir de un mensaje de este usuario.
                        self._conn.execute("DELETE FROM decision_history WHERE id = ?", (row["id"],))
                        counts["decisions"] += 1
                        continue
                    new, changed = self._scrub_user_record(data, user_id)
                    if changed:
                        self._conn.execute(
                            "UPDATE decision_history SET data = ? WHERE id = ?",
                            (json.dumps(new), row["id"]),
                        )
                        counts["decisions"] += 1

                self._conn.commit()
        except sqlite3.Error as e:
            print(f"⚠️  Error borrando datos éticos del usuario: {e}")
            raise

        # La copia en memoria de los patrones aprendidos debe reflejar la BD.
        self.decision_history = self._load_decision_history()
        return counts

    # ==================== PERSISTENCIA (SQLite) ====================

    def _load_consultations(self) -> List[Dict]:
        try:
            with self._lock:
                rows = self._conn.execute(
                    "SELECT data FROM consultations ORDER BY consultation_id ASC"
                ).fetchall()
            return [json.loads(row["data"]) for row in rows]
        except (sqlite3.DatabaseError, json.JSONDecodeError) as e:
            print(f"⚠️  Error cargando consultas: {e}")
            return []

    def _save_consultations(self, consultations: List[Dict]) -> None:
        try:
            with self._lock:
                self._conn.execute("DELETE FROM consultations")
                self._conn.executemany(
                    "INSERT INTO consultations (consultation_id, data) VALUES (?, ?)",
                    [(c["consultation_id"], json.dumps(c)) for c in consultations],
                )
                self._conn.commit()
        except (sqlite3.Error, TypeError, KeyError) as e:
            print(f"⚠️  Error guardando consultas: {e}")

    def _load_decision_history(self) -> List[Dict]:
        try:
            with self._lock:
                rows = self._conn.execute(
                    "SELECT data FROM decision_history ORDER BY id ASC"
                ).fetchall()
            return [json.loads(row["data"]) for row in rows]
        except (sqlite3.DatabaseError, json.JSONDecodeError) as e:
            print(f"⚠️  Error cargando historial de decisiones: {e}")
            return []

    def _save_decision_history(self) -> None:
        try:
            with self._lock:
                self._conn.execute("DELETE FROM decision_history")
                self._conn.executemany(
                    "INSERT INTO decision_history (data) VALUES (?)",
                    [(json.dumps(d),) for d in self.decision_history],
                )
                self._conn.commit()
        except (sqlite3.Error, TypeError) as e:
            print(f"⚠️  Error guardando historial de decisiones: {e}")

    def get_ethics_report(self) -> Dict:
        consultations = self._load_consultations()

        pending = sum(1 for c in consultations if c.get('status') == ConsultationStatus.PENDING.value)
        # "resolved" = cualquier consulta que ya no está pendiente.
        # Antes solo se contaba el literal 'resolved', pero ese valor
        # ya no existe en el modelo de 6 estados — ahora una consulta
        # resuelta tiene status approved/rejected/redirected/etc.
        resolved = sum(1 for c in consultations if c.get('status') != ConsultationStatus.PENDING.value)

        approved = sum(
            1 for c in consultations
            if c.get('fons_decision') is not None
            and isinstance(c.get('fons_decision'), dict)
            and c.get('fons_decision', {}).get('approved', False)
        )

        return {
            'total_consultations': len(consultations),
            'pending_consultations': pending,
            'resolved_consultations': resolved,
            'approved_responses': approved,
            'learned_decisions': len(self.decision_history),
            'core_principles': self.core_principles,
            'last_consultation': consultations[-1] if consultations else None
        }

    def print_ethics_status(self) -> None:
        report = self.get_ethics_report()
        print(f"Total: {report['total_consultations']}")