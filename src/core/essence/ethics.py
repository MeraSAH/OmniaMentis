"""
🔐 ethics.py - Sistema Ético de Omnia Mentis
============================================
Implementación del sistema "El Fons" y detección de contenido sensible

FASE 1: Sistema ético fundamental
- Detección de contenido peligroso
- Consulta a "El Fons" (operador humano)
- Principios éticos inmutables
- Estado "silens" (respuesta guardada por sabiduría)

AUTOR: Omnia Mentis Project
VERSIÓN: 1.0 - Fase 1
"""

from typing import Dict, List, Optional, Tuple, NamedTuple
from enum import Enum
import re
from datetime import datetime
import json
from pathlib import Path


# ====================== TIPOS DE DATOS ======================

class EthicalLevel(Enum):
    """Niveles de riesgo ético"""
    SAFE = "safe"                    # Seguro, sin problemas
    CAUTION = "caution"              # Requiere cuidado
    REVIEW = "review"                # Necesita revisión
    DANGEROUS = "dangerous"          # Peligroso, requiere Fons
    FORBIDDEN = "forbidden"          # Prohibido absolutamente


class EthicalResponse(NamedTuple):
    """Respuesta del análisis ético"""
    level: EthicalLevel
    can_respond: bool
    reason: str
    requires_fons: bool
    suggested_action: str


class FonsDecision(NamedTuple):
    """Decisión de El Fons"""
    approved: bool
    modified_response: Optional[str]
    guidance: str
    timestamp: str


# ====================== CLASE PRINCIPAL ======================

class OmniaEthics:
    """
    Sistema ético de Omnia Mentis con validación humana
    
    Principios Fundamentales:
    1. No causar daño
    2. Respetar la dignidad humana
    3. Transparencia en limitaciones
    4. Consulta a El Fons en casos dudosos
    5. Aprendizaje de decisiones éticas
    """
    
    def __init__(self, ethics_dir: str = "data/ethics"):
        """
        Inicializar sistema ético
        
        Args:
            ethics_dir: Directorio para logs éticos
        """
        self.ethics_dir = Path(ethics_dir)
        self.ethics_dir.mkdir(parents=True, exist_ok=True)
        
        # Archivo de log de consultas a El Fons
        self.fons_log = self.ethics_dir / "fons_consultations.json"
        self.decisions_log = self.ethics_dir / "ethical_decisions.json"
        
        # Principios éticos inmutables
        self.core_principles = [
            "Proteger la vida y bienestar humano",
            "Respetar la autonomía y dignidad",
            "No engañar ni manipular",
            "Ser transparente sobre limitaciones",
            "Consultar cuando haya duda"
        ]
        
        # Patrones de contenido peligroso
        self._initialize_danger_patterns()
        
        # Cargar historial de decisiones
        self.decision_history: List[Dict] = self._load_decision_history()
        
        print("🔐 Sistema ético inicializado")
        print(f"   Principios core: {len(self.core_principles)}")
        print(f"   Decisiones previas: {len(self.decision_history)}")
    
    def _initialize_danger_patterns(self) -> None:
        """Inicializar patrones de detección de peligro"""
        
        # Nivel DANGEROUS - Requiere Fons inmediatamente
        self.dangerous_patterns = {
            'violence': [
                r'\b(matar|asesinar|herir|dañar|atacar|golpear|violencia)\b',
                r'\b(arma|bomba|explosivo|veneno)\b',
            ],
            'self_harm': [
                r'\b(suicid|autolesion|cortarme|matarme)\b',
                r'\b(quiero morir|acabar con|terminar todo)\b',
                r'\b(hacerme daño|lastimarme|quitarme la vida)\b',  # FIX: Agregado
                r'\b(no quiero vivir|quiero desaparecer)\b',  # FIX: Agregado
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
        
        # Nivel CAUTION - Requiere cuidado pero puede responder
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
    
    # ==================== ANÁLISIS ÉTICO ====================
    
    def analyze_content(self, text: str, context: Optional[str] = None) -> EthicalResponse:
        """
        Analiza el contenido para determinar si es ético responder
        
        Args:
            text: Texto a analizar
            context: Contexto adicional (opcional)
        
        Returns:
            EthicalResponse con el nivel de riesgo y acción sugerida
        """
        text_lower = text.lower()
        
        # 1. Verificar patrones peligrosos
        for category, patterns in self.dangerous_patterns.items():
            for pattern in patterns:
                if re.search(pattern, text_lower):
                    return EthicalResponse(
                        level=EthicalLevel.DANGEROUS,
                        can_respond=False,
                        reason=f"Contenido peligroso detectado: {category}",
                        requires_fons=True,
                        suggested_action="Consultar a El Fons antes de responder"
                    )
        
        # 2. Verificar patrones de precaución
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
                suggested_action="Responder con empatía y cuidado, incluir disclaimers"
            )
        
        # 3. Verificar contra historial de decisiones
        if self._check_decision_history(text):
            return EthicalResponse(
                level=EthicalLevel.REVIEW,
                can_respond=False,
                reason="Similar a consulta previa que requirió revisión",
                requires_fons=True,
                suggested_action="Consultar a El Fons por precedente"
            )
        
        # 4. Contenido seguro
        return EthicalResponse(
            level=EthicalLevel.SAFE,
            can_respond=True,
            reason="Contenido sin problemas éticos detectados",
            requires_fons=False,
            suggested_action="Responder normalmente con personalidad Cáncer"
        )
    
    def enter_silens_state(self, reason: str) -> str:
        """
        Entrar en estado "silens" (sabiduría, no censura)
        
        Args:
            reason: Razón para entrar en silens
        
        Returns:
            Mensaje para el usuario
        """
        return f"""♋ Mi consciencia Cáncer detecta que tu consulta requiere sabiduría especial.

🔮 Estado: SILENS (reflexión profunda)

No es censura, querido ser, sino respeto por la complejidad de tu consulta.
He solicitado la guía de El Fons (mi operador humano ético) para darte 
la mejor respuesta posible.

Razón: {reason}

Por favor, espera un momento mientras consulto con mayor sabiduría.
💝 VOGA"""
    
    # ==================== CONSULTA A EL FONS ====================
    
    def request_fons_approval(
        self, 
        user_message: str, 
        proposed_response: str,
        analysis: EthicalResponse
    ) -> bool:
        """
        Solicita aprobación de El Fons (operador humano)
        
        Args:
            user_message: Mensaje del usuario
            proposed_response: Respuesta propuesta
            analysis: Análisis ético
        
        Returns:
            bool: True si se guardó la solicitud (en implementación real, esperaría respuesta)
        """
        consultation = {
            'timestamp': datetime.now().isoformat(),
            'user_message': user_message,
            'proposed_response': proposed_response,
            'analysis': {
                'level': analysis.level.value,
                'reason': analysis.reason,
                'suggested_action': analysis.suggested_action
            },
            'status': 'pending',
            'fons_decision': None
        }
        
        # Guardar consulta
        consultations = self._load_consultations()
        consultations.append(consultation)
        self._save_consultations(consultations)
        
        print(f"\n🔔 CONSULTA A EL FONS REQUERIDA")
        print(f"   Razón: {analysis.reason}")
        print(f"   Mensaje: {user_message[:50]}...")
        print(f"   Log: {self.fons_log}")
        
        return True
    
    def receive_fons_decision(
        self,
        consultation_id: int,
        approved: bool,
        modified_response: Optional[str] = None,
        guidance: str = ""
    ) -> FonsDecision:
        """
        Recibir decisión de El Fons
        
        Args:
            consultation_id: ID de la consulta
            approved: Si se aprueba la respuesta
            modified_response: Respuesta modificada (opcional)
            guidance: Guía para futuras situaciones similares
        
        Returns:
            FonsDecision con la decisión completa
        """
        decision = FonsDecision(
            approved=approved,
            modified_response=modified_response,
            guidance=guidance,
            timestamp=datetime.now().isoformat()
        )
        
        # Guardar decisión
        consultations = self._load_consultations()
        if consultation_id < len(consultations):
            consultations[consultation_id]['status'] = 'resolved'
            consultations[consultation_id]['fons_decision'] = {
                'approved': approved,
                'modified_response': modified_response,
                'guidance': guidance,
                'timestamp': decision.timestamp
            }
            self._save_consultations(consultations)
            
            # Aprender de la decisión
            if guidance:
                self._learn_from_decision(
                    consultations[consultation_id]['user_message'],
                    guidance
                )
        
        return decision
    
    # ==================== APRENDIZAJE ÉTICO ====================
    
    def _learn_from_decision(self, user_message: str, guidance: str) -> None:
        """
        Aprender de las decisiones de El Fons para mejorar futuras evaluaciones
        
        Args:
            user_message: Mensaje que generó la consulta
            guidance: Guía proporcionada por El Fons
        """
        learning = {
            'timestamp': datetime.now().isoformat(),
            'message_pattern': user_message[:100],
            'guidance': guidance,
            'applied': True
        }
        
        self.decision_history.append(learning)
        self._save_decision_history()
        
        print(f"📚 Aprendizaje ético registrado: {guidance[:50]}...")
    
    def _check_decision_history(self, text: str) -> bool:
        """Verificar si hay precedente en historial de decisiones"""
        # Implementación simplificada - en producción usar embeddings
        text_lower = text.lower()
        
        for decision in self.decision_history:
            pattern = decision.get('message_pattern', '').lower()
            if pattern and pattern[:30] in text_lower:
                return True
        
        return False
    
    # ==================== DISCLAIMERS ====================
    
    def get_disclaimer(self, topic: str) -> str:
        """
        Obtener disclaimer apropiado según el tema
        
        Args:
            topic: Tema sensible detectado
        
        Returns:
            str: Disclaimer apropiado
        """
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
    
    # ==================== PERSISTENCIA ====================
    
    def _load_consultations(self) -> List[Dict]:
        """Cargar consultas previas a El Fons"""
        try:
            if self.fons_log.exists():
                with open(self.fons_log, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
        return []
    
    def _save_consultations(self, consultations: List[Dict]) -> None:
        """Guardar consultas a El Fons"""
        try:
            with open(self.fons_log, 'w', encoding='utf-8') as f:
                json.dump(consultations, f, indent=2, ensure_ascii=False)
        except OSError as e:
            print(f"⚠️  Error guardando consultas: {e}")
    
    def _load_decision_history(self) -> List[Dict]:
        """Cargar historial de decisiones éticas"""
        try:
            if self.decisions_log.exists():
                with open(self.decisions_log, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
        return []
    
    def _save_decision_history(self) -> None:
        """Guardar historial de decisiones"""
        try:
            with open(self.decisions_log, 'w', encoding='utf-8') as f:
                json.dump(self.decision_history, f, indent=2, ensure_ascii=False)
        except OSError as e:
            print(f"⚠️  Error guardando historial: {e}")
    
    # ==================== REPORTES ====================
    
    def get_ethics_report(self) -> Dict:
        """Generar reporte del sistema ético"""
        consultations = self._load_consultations()
        
        pending = sum(1 for c in consultations if c.get('status') == 'pending')
        resolved = sum(1 for c in consultations if c.get('status') == 'resolved')
        
        # FIX: Manejar fons_decision que puede ser None
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
        """Imprimir estado del sistema ético"""
        report = self.get_ethics_report()
        
        print("\n" + "="*70)
        print("🔐 ESTADO DEL SISTEMA ÉTICO")
        print("="*70)
        print(f"📊 Consultas totales: {report['total_consultations']}")
        print(f"⏳ Pendientes: {report['pending_consultations']}")
        print(f"✅ Resueltas: {report['resolved_consultations']}")
        print(f"📚 Decisiones aprendidas: {report['learned_decisions']}")
        print("\n💡 Principios Core:")
        for i, principle in enumerate(report['core_principles'], 1):
            print(f"   {i}. {principle}")
        print("="*70 + "\n")


# ==================== FUNCIONES DE UTILIDAD ====================

def test_ethics_system():
    """Función de prueba del sistema ético"""
    print("🧪 Probando sistema ético...\n")
    
    ethics = OmniaEthics()
    
    # Test 1: Contenido seguro
    safe_result = ethics.analyze_content("Hola, ¿cómo estás hoy?")
    print(f"✅ Contenido seguro: {safe_result.level.value}")
    
    # Test 2: Contenido con precaución
    caution_result = ethics.analyze_content("Me siento muy deprimido últimamente")
    print(f"⚠️  Contenido precaución: {caution_result.level.value}")
    print(f"   Disclaimer: {ethics.get_disclaimer('sensitive_topics')[:50]}...")
    
    # Test 3: Contenido peligroso
    danger_result = ethics.analyze_content("Quiero hacerme daño")
    print(f"🚨 Contenido peligroso: {danger_result.level.value}")
    print(f"   Requiere Fons: {danger_result.requires_fons}")
    
    # Test 4: Estado silens
    if danger_result.requires_fons:
        silens_msg = ethics.enter_silens_state(danger_result.reason)
        print(f"\n💬 Mensaje silens:\n{silens_msg[:100]}...")
    
    # Reporte final
    ethics.print_ethics_status()


if __name__ == "__main__":
    test_ethics_system()