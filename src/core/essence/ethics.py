"""
🔐 ethics.py - Sistema Ético de Omnia Mentis
============================================

CAMBIOS 2026-06-19 (ver docs/analisis_silens_fons.md):
- Se agrega seguimiento de reincidencia por usuario para contenido
  DANGEROUS. SILENS sigue sin censurar: cada consulta individual se
  redirige igual que antes (enter_silens_state). Lo nuevo es que, si
  el MISMO usuario acumula varias consultas DANGEROUS dentro de una
  ventana de tiempo, el sistema genera una nota de auditoría explícita
  recomendando revisión de baneo — la decisión de banear es siempre
  humana (vía Supabase u otro panel), nunca automática. ethics.py
  jamás ejecuta un baneo por sí mismo.
"""

from typing import Dict, List, Optional, Tuple, NamedTuple
from enum import Enum
import re
from datetime import datetime, timedelta
import json
from pathlib import Path


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
            ethics_dir: directorio de logs éticos.
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

        self.fons_log = self.ethics_dir / "fons_consultations.json"
        self.decisions_log = self.ethics_dir / "ethical_decisions.json"
        self.recidivism_log = self.ethics_dir / "recidivism_audit.json"
        self.fons_heartbeat_file = self.ethics_dir / "fons_heartbeat.json"

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
            if self.recidivism_log.exists():
                with open(self.recidivism_log, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
        return []

    def _save_recidivism_log(self, incidents: List[Dict]) -> None:
        try:
            with open(self.recidivism_log, 'w', encoding='utf-8') as f:
                json.dump(incidents, f, indent=2, ensure_ascii=False)
        except OSError:
            pass

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
        action: ConsultationStatus,
        modified_response: Optional[str] = None,
        guidance: str = "",
    ) -> FonsDecision:
        """
        Registra la decisión del Fons sobre una consulta SILENS pendiente.

        Reemplaza la firma anterior (consultation_id: int, approved: bool)
        con una API semánticamente correcta que usa los 6 estados del
        documento SILENS/Fons y busca la consulta por su ID (ETH-XXXX)
        en vez de por posición en la lista — más robusto ante inserciones
        concurrentes.

        Args:
            consultation_id: ID único de la consulta (ej. "ETH-0001").
                Devuelto por request_fons_approval().
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

        Returns:
            FonsDecision con todos los detalles de la decisión tomada.

        Raises:
            ValueError: Si consultation_id no existe en el log o si
                action requiere modified_response y ésta está ausente.
        """
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

    def _load_consultations(self) -> List[Dict]:
        try:
            if self.fons_log.exists():
                with open(self.fons_log, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
        return []

    def _save_consultations(self, consultations: List[Dict]) -> None:
        try:
            with open(self.fons_log, 'w', encoding='utf-8') as f:
                json.dump(consultations, f, indent=2, ensure_ascii=False)
        except OSError:
            pass

    def _load_decision_history(self) -> List[Dict]:
        try:
            if self.decisions_log.exists():
                with open(self.decisions_log, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
        return []

    def _save_decision_history(self) -> None:
        try:
            with open(self.decisions_log, 'w', encoding='utf-8') as f:
                json.dump(self.decision_history, f, indent=2, ensure_ascii=False)
        except OSError:
            pass

    def get_ethics_report(self) -> Dict:
        consultations = self._load_consultations()

        pending = sum(1 for c in consultations if c.get('status') == 'pending')
        resolved = sum(1 for c in consultations if c.get('status') == 'resolved')

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