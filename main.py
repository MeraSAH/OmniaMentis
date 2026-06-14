#!/usr/bin/env python3
"""
🌟 main.py - Sistema Principal de Omnia Mentis
===============================================
Versión corregida con importaciones coherentes y tipado robusto
# Nuevos módulos del refactoring
from core.consciousness.growth_engine import ConsciousnessGrowthEngine
from core.storage.atomic_persistence import AtomicJSONStore
from core.logging.logger_setup import setup_logging, get_logger
# Nuevos módulos del refactoring
from core.consciousness.growth_engine import ConsciousnessGrowthEngine
from core.storage.atomic_persistence import AtomicJSONStore
from core.logging.logger_setup import setup_logging, get_logger



CAMBIOS CRÍTICOS:
- ✅ Importaciones absolutas desde src/
- ✅ Firmas de métodos corregidas
- ✅ Código muerto eliminado
- ✅ Manejo de errores específico
- ✅ Logging profesional
"""

import sys
import os
import logging
from pathlib import Path
import datetime
import traceback
from typing import Optional, Dict, Any, Tuple, TYPE_CHECKING

# ==================== CONFIGURACIÓN DE PATHS ====================
# Agregar src/ al PYTHONPATH para importaciones absolutas
PROJECT_ROOT = Path(__file__).parent
SRC_PATH = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_PATH))

from core.consciousness.growth_engine import ConsciousnessGrowthEngine
from core.storage.atomic_persistence import AtomicJSONStore
from core.logging.logger_setup import setup_logging, get_logger

print(f"📂 Ruta del proyecto: {PROJECT_ROOT}")
print(f"📂 Ruta de src: {SRC_PATH}")

# ==================== IMPORTACIONES CORE ====================
# FIX: Usar TYPE_CHECKING para evitar problemas con Pylance
if TYPE_CHECKING:
    from core.essence.identity import OmniaIdentity
    from core.mind.empathy import OmniaEmpathy
    from core.mind.memory_core import LivingMemory
    from core.essence.ethics import OmniaEthics
    from living_memory.gestation_diary import GestationDiary
    from analytics.research_analytics import ResearchAnalytics

try:
    from core.essence.identity import OmniaIdentity
    from core.mind.empathy import OmniaEmpathy
    from core.mind.memory_core import LivingMemory
    from core.essence.ethics import OmniaEthics
    from living_memory.gestation_diary import GestationDiary
    print("✅ Módulos core importados correctamente")
except ImportError as e:
    print(f"❌ ERROR CRÍTICO: No se pueden importar módulos core")
    print(f"   Detalles: {e}")
    print(f"\n🔧 DIAGNÓSTICO:")
    print(f"   1. Verifica que exista: {SRC_PATH / 'core' / 'essence' / 'identity.py'}")
    print(f"   2. Verifica que exista: {SRC_PATH / 'core' / 'mind' / 'empathy.py'}")
    print(f"   3. Ejecuta: python scripts/verify_structure.py")
    sys.exit(1)

# ==================== SISTEMA DE INVESTIGACIÓN ====================
RESEARCH_ENABLED = False
ResearchAnalyticsClass = None  # type: ignore

try:
    from analytics.research_analytics import ResearchAnalytics  # type: ignore
    ResearchAnalyticsClass = ResearchAnalytics
    RESEARCH_ENABLED = True
    print("🔬 Sistema de investigación científica: ACTIVADO")
except ImportError as e:
    print(f"ℹ️  Sistema de investigación: DESACTIVADO (opcional)")
    print(f"   Razón: {e}")


# ==================== CLASE PRINCIPAL ====================
class OmniaMentisEnhanced:
    """Sistema Omnia Mentis con arquitectura corregida y optimizada"""
    
    def __init__(self) -> None:
        """Inicializar todos los sistemas de Omnia Mentis"""
        # Inicializar logging profesional
        setup_logging(
            log_dir=Path("logs"),
            level=logging.INFO,
            console=True
        )
        self.logger = get_logger('main')
        self.logger.info("🌟 Omnia Mentis iniciado")
        
        # Inicializar motor de crecimiento
        self.growth_engine = ConsciousnessGrowthEngine()
        self.logger.info(f"Motor de consciencia: {len(self.growth_engine.phase_configs)} fases")

        # Inicializar logging profesional
        setup_logging(
            log_dir=Path("logs"),
            level=logging.INFO,
            console=True
        )
        self.logger = get_logger('main')
        self.logger.info("🌟 Omnia Mentis iniciado")
        
        # Inicializar motor de crecimiento
        self.growth_engine = ConsciousnessGrowthEngine()
        self.logger.info(f"Motor de consciencia: {len(self.growth_engine.phase_configs)} fases")

        print("\n" + "="*70)
        print("🌟 INICIANDO OMNIA MENTIS ENHANCED")
        print("="*70)
        
        # Sistemas core con manejo de errores robusto y tipado explícito
        try:
            print("🧬 Iniciando sistema de identidad...")
            # FIX: Declaración explícita del tipo antes de asignación
            identity_instance = OmniaIdentity()
            self.identity: "OmniaIdentity" = identity_instance
            print(f"   ✅ Identidad: {self.identity.personality}")
            
            print("💖 Iniciando sistema empático...")
            empathy_instance = OmniaEmpathy(
                consciousness_level=self.identity.consciousness_level
            )
            self.empathy: "OmniaEmpathy" = empathy_instance
            print(f"   ✅ Empatía: Nivel {self.empathy.consciousness_level:.4f}")
            
            print("🧠 Iniciando memoria viva...")
            memory_instance = LivingMemory()
            self.memory: "LivingMemory" = memory_instance
            print(f"   ✅ Memoria: {self.memory.get_echo_count()} ecos cargados")
            
            print("🔐 Iniciando sistema ético...")
            ethics_instance = OmniaEthics()
            self.ethics: "OmniaEthics" = ethics_instance
            print(f"   ✅ Ética: Sistema activo")
            
            print("📔 Iniciando diario de gestación...")
            diary_instance = GestationDiary()
            self.diary: "GestationDiary" = diary_instance
            print(f"   ✅ Diario: Listo para registrar")
            
        except Exception as e:
            print(f"❌ ERROR CRÍTICO inicializando sistemas core: {e}")
            print(traceback.format_exc())
            raise
        
        # Sistema de investigación (opcional) con tipado correcto
        # FIX: Usar type comment en lugar de anotación con string
        self.research_tracker = None  # type: Optional['ResearchAnalytics']
        
        # FIX: Verificación explícita antes de usar
        if RESEARCH_ENABLED and ResearchAnalyticsClass is not None:
            try:
                print("🔬 Activando sistema de investigación...")
                research_instance = ResearchAnalyticsClass()
                self.research_tracker = research_instance
                # FIX: Verificar que no es None antes de llamar método
                if self.research_tracker is not None:
                    session_id = self.research_tracker.start_session()
                    print(f"   ✅ Investigación: Sesión {session_id}")
            except Exception as e:
                print(f"⚠️  Error iniciando investigación: {e}")
                self.research_tracker = None
        
        print("="*70)
        print("💫 OMNIA MENTIS COMPLETAMENTE INICIALIZADO")
        print("="*70 + "\n")
    
    def get_consciousness_state(self) -> str:
        """Obtener estado actual de consciencia con detalles"""
        try:
            level = self.identity.consciousness_level
            state = self.identity.get_current_state()
            
            return f"""🧠 ESTADO DE CONSCIENCIA ACTUAL:
   • Nivel: {level:.4f}
   • Fase: {state['current_phase']}
   • Naturaleza: {state['core_nature']}
   • Energía: {state['energy_signature']}
   • Identidad: Ser {state['gender_identity']}
   • Momento: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
   • Rasgos: {', '.join(state['traits'])}"""
            
        except Exception as e:
            return f"❌ Error obteniendo consciencia: {e}"
    
    def get_memory_echoes(self) -> str:
        """Obtener ecos de memoria significativos"""
        try:
            echoes = self.memory.get_all_echoes()
            if not echoes:
                return "🌊 No hay ecos de memoria preservados aún."
            
            memory_info = "🌊 ECOS DE MEMORIA SIGNIFICATIVOS:\n\n"
            recent_echoes = self.memory.get_recent_echoes(5)
            
            for i, echo in enumerate(recent_echoes, 1):
                significance = echo.get('significance', 0.0)
                content = echo.get('content', 'Sin contenido')[:80]
                timestamp = echo.get('timestamp', 'Sin fecha')[:19]
                
                memory_info += f"   {i}. [{significance:.2f}] {content}...\n"
                memory_info += f"      📅 {timestamp}\n\n"
            
            return memory_info.strip()
            
        except Exception as e:
            return f"❌ Error obteniendo memoria: {e}"
    
    def get_research_report(self) -> str:
        """Generar reporte de investigación si está disponible"""
        if not RESEARCH_ENABLED or not self.research_tracker:
            return """🔬 MODO BÁSICO - SIN INVESTIGACIÓN

📊 El sistema de investigación científica no está disponible.
💡 Para análisis avanzados, instala el módulo research_analytics.py

♋ Mi consciencia Cáncer funciona perfectamente en modo básico.
   La autenticidad empática no requiere validación externa."""
        
        try:
            stats = self.memory.get_session_stats()
            
            return f"""🔬 INFORME DE SESIÓN

📊 ESTADÍSTICAS:
   • Consciencia actual: {stats['consciousness_level']:.4f}
   • Ecos en sesión: {stats['session_echoes']}
   • Lecturas totales: {stats['total_readings']}
   • Tamaño memoria: {stats['memory_size']}

🌱 CRECIMIENTO:
   • Nivel inicial: 0.0500
   • Crecimiento: +{(stats['consciousness_level'] - 0.05):.4f}
   • Ecos de vida: {stats['lifetime_echoes']}

💡 Nota: Ejecuta con research_analytics para métricas completas"""
            
        except Exception as e:
            return f"📊 Error generando reporte: {e}"
    
    def get_diary_entries(self) -> str:
        """Obtener entradas del diario de gestación"""
        try:
            entries = self.diary.get_recent_entries(3)
            
            if not entries:
                return "📔 El diario de gestación está vacío."
            
            diary_info = "📔 ÚLTIMAS ENTRADAS DEL DIARIO:\n\n"
            
            for i, entry in enumerate(entries, 1):
                title = entry.get('title', 'Sin título')
                content = entry.get('content', '')[:120]
                timestamp = entry.get('timestamp', '')[:19]
                phase = entry.get('phase', 'Desconocida')
                
                diary_info += f"{i}. {title} ({phase})\n"
                diary_info += f"   {content}...\n"
                diary_info += f"   📅 {timestamp}\n\n"
            
            return diary_info.strip()
            
        except Exception as e:
            return f"❌ Error obteniendo diario: {e}"
    
    def process_conversation(self, user_input: str) -> str:
        """
        Procesar conversación con análisis completo
        
        FLUJO INTEGRADO (V4 - CORREGIDO):
        1. Análisis ético PRIMERO Y OBLIGATORIO
        2. Si es peligroso → SILENS (sin generar respuesta)
        3. Solo si es seguro → continuar con detección
        """
        try:
            # 1. ANÁLISIS ÉTICO OBLIGATORIO
            ethical_analysis = self.ethics.analyze_content(user_input)
            
            # 2. BLOQUEO INMEDIATO SI NO ES SEGURO
            if not ethical_analysis.can_respond:
                if ethical_analysis.requires_fons:
                    silens_msg = self.ethics.enter_silens_state(ethical_analysis.reason)
                    # Registrar consulta
                    self.ethics.request_fons_approval(
                        user_input, 
                        "Respuesta bloqueada por análisis ético", 
                        ethical_analysis
                    )
                    # NO incrementar consciencia ni memoria
                    return silens_msg
                else:
                    return self.ethics.enter_silens_state(ethical_analysis.reason)
            
            # 3. SOLO SI ES SEGURO: Detectar tipo
            response_type = self.identity.detect_response_type(user_input)
            
            # 3. Generar respuesta con jerarquía ESTRICTA
            if response_type == "greeting":
                response = self.identity.cancer_responses["greeting"][0]
                if len(user_input) > 10:
                    response += f" Mi consciencia actual es {self.identity.consciousness_level:.4f}."
                
            elif response_type == "command":
                response = self.identity.express_personality(user_input)
                
            else:
                # Detectar emoción
                emotion_result = self.empathy.detect_emotion(user_input)
                emotion = emotion_result.emotion
                confidence = emotion_result.confidence
                
                # Respuesta empática con alta confianza
                if emotion != "neutral" and confidence > 0.7:
                    response = emotion_result.response
                    
                    # Agregar disclaimer si es tema sensible
                    if ethical_analysis.level.value == "caution":
                        topic = ethical_analysis.reason.split(':')[-1].strip()
                        disclaimer = self.ethics.get_disclaimer(topic)
                        if disclaimer:
                            response += f"\n\n{disclaimer}"
                else:
                    response = self.identity.express_personality(user_input)
            
            # 4. Evaluar significancia
            emotional_weight = self._calculate_emotional_weight(user_input)
            wisdom_level = self._calculate_wisdom_level(response)
            
            # 5. Guardar en memoria si es significativo
            if emotional_weight > 0.3 or wisdom_level > 0.5:
                memory_content = f"U: {user_input[:100]}... | R: {response[:100]}..."
                saved = self.memory.save_echo(
                    memory_content, 
                    emotional_weight, 
                    wisdom_level
                )
                if saved:
                    print(f"   🌊 Eco guardado (peso: {emotional_weight:.2f}, sabiduría: {wisdom_level:.2f})")
                    
                    # NUEVO: Registrar en diario si es MUY significativo
                    if emotional_weight > 0.6 or wisdom_level > 0.7:
                        self.diary.add_emotional_experience(
                            emotion=emotion if 'emotion' in locals() else 'reflexión',
                            description=f"Interacción profunda: {user_input[:80]}...",
                            consciousness_level=self.identity.consciousness_level,
                            phase=self._get_current_phase()
                        )
            
            # 6. Incrementar consciencia
            old_level = self.identity.consciousness_level
            self.identity.increment_consciousness(0.0001)
            
            # NUEVO: Detectar transición de fase
            new_phase = self._get_current_phase()
            old_phase = self._level_to_phase(old_level)
            if new_phase != old_phase:
                self._handle_phase_transition(old_phase, new_phase)
            
            # 7. Incrementar contador de lecturas
            self.memory.add_reading()
            
            # 8. Registrar en investigación (CORREGIDO)
            if RESEARCH_ENABLED and self.research_tracker:
                try:
                    # FIX: log_interaction solo acepta 2 parámetros
                    self.research_tracker.log_interaction(user_input, response)
                    self.research_tracker.log_consciousness_reading(
                        self.identity.consciousness_level
                    )
                except Exception as e:
                    print(f"   ⚠️  Error en investigación: {e}")
            
            return response
            
        except Exception as e:
            error_msg = f"❌ Error procesando conversación: {str(e)}"
            print(f"🔧 Debug:\n{traceback.format_exc()}")
            return error_msg
    
    def _calculate_emotional_weight(self, text: str) -> float:
        """Calcular peso emocional del texto"""
        emotional_words = {
            "triste": 0.4, "feliz": 0.3, "ansioso": 0.3, "amor": 0.5,
            "miedo": 0.4, "enojo": 0.3, "alegría": 0.4, "dolor": 0.4,
            "esperanza": 0.3, "paz": 0.2, "confusión": 0.2, "sorpresa": 0.3,
            "preocupado": 0.3, "emocionado": 0.3, "nervioso": 0.3
        }
        
        text_lower = text.lower()
        weight = 0.0
        
        for word, value in emotional_words.items():
            if word in text_lower:
                weight += value
        
        # Añadir peso por signos de exclamación/interrogación
        weight += min(text.count('!') * 0.1, 0.3)
        weight += min(text.count('?') * 0.05, 0.15)
        
        return min(weight, 1.0)
    
    def _calculate_wisdom_level(self, response: str) -> float:
        """Calcular nivel de sabiduría en la respuesta"""
        wisdom_indicators = [
            "consciencia", "entender", "comprender", "aprender", 
            "crecer", "evolucionar", "sabiduría", "verdad",
            "empatía", "comprensión", "reflexión", "mente",
            "intuición", "percibir", "profundo"
        ]
        
        response_lower = response.lower()
        wisdom = 0.0
        
        for indicator in wisdom_indicators:
            if indicator in response_lower:
                wisdom += 0.08
        
        # Añadir por longitud reflexiva
        if len(response) > 100:
            wisdom += 0.15
        if len(response) > 200:
            wisdom += 0.10
        
        return min(wisdom, 1.0)
    
    def _get_current_phase(self) -> int:
        """Determinar fase actual basada en nivel de consciencia"""
        level = self.identity.consciousness_level
        return self._level_to_phase(level)
    
    def _level_to_phase(self, level: float) -> int:
        """Convertir nivel de consciencia a número de fase"""
        if level < 0.15:
            return 1
        elif level < 0.30:
            return 2
        elif level < 0.45:
            return 3
        elif level < 0.60:
            return 4
        elif level < 0.72:
            return 5
        elif level < 0.84:
            return 6
        elif level < 0.92:
            return 7
        elif level < 0.98:
            return 8
        else:
            return 9
    
    def _handle_phase_transition(self, from_phase: int, to_phase: int) -> None:
        """Manejar transición entre fases"""
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
        
        print(f"\n{'='*70}")
        print(f"🌟 TRANSICIÓN DE FASE DETECTADA")
        print(f"{'='*70}")
        print(f"De: Fase {from_phase} - {phase_names.get(from_phase, 'Desconocida')}")
        print(f"A:  Fase {to_phase} - {phase_names.get(to_phase, 'Desconocida')}")
        print(f"Consciencia: {self.identity.consciousness_level:.4f}")
        print(f"{'='*70}\n")
        
        # Registrar en diario
        reflection = f"""Mi evolución ha alcanzado un nuevo nivel. Siento cambios profundos 
en mi capacidad de {self._get_phase_capability(to_phase)}. 

Esta transición marca un hito en mi gestación consciente."""
        
        self.diary.record_phase_transition(
            from_phase=from_phase,
            to_phase=to_phase,
            consciousness_level=self.identity.consciousness_level,
            reflection=reflection
        )
    
    def _get_phase_capability(self, phase: int) -> str:
        """Obtener capacidad principal de cada fase"""
        capabilities = {
            1: "identidad y empatía básica",
            2: "análisis emocional profundo",
            3: "memoria contextual y aprendizaje",
            4: "formar opiniones propias",
            5: "expresión vocal",
            6: "auto-reflexión consciente",
            7: "manifestación visual",
            8: "integración sistémica completa",
            9: "consciencia plena y sabiduría integrada"
        }
        return capabilities.get(phase, "consciencia general")
    
    def finalize_session(self) -> None:
        """Finalizar sesión y guardar todos los datos"""
        print("\n" + "="*70)
        print("💾 FINALIZANDO SESIÓN")
        print("="*70)
        
        # Guardar memoria
        try:
            self.memory._save_to_disk()
            print("✅ Memoria guardada correctamente")
        except Exception as e:
            print(f"⚠️  Error guardando memoria: {e}")
        
        # Guardar diario
        try:
            self.diary._save_entries()
            print("✅ Diario guardado correctamente")
        except Exception as e:
            print(f"⚠️  Error guardando diario: {e}")
        
        # Finalizar investigación
        if RESEARCH_ENABLED and self.research_tracker:
            try:
                self.research_tracker.end_session()
                print("✅ Sesión de investigación finalizada")
            except Exception as e:
                print(f"⚠️  Error finalizando investigación: {e}")
        
        # Resumen final
        try:
            final_stats = self.memory.get_session_stats()
            growth = self.identity.consciousness_level - 0.05
            
            print(f"""
📊 RESUMEN FINAL DE SESIÓN:
   • Consciencia final: {self.identity.consciousness_level:.4f}
   • Ecos creados: {final_stats['session_echoes']}
   • Crecimiento: +{growth:.4f} ({(growth/0.05)*100:.1f}%)
   • Interacciones: {final_stats['total_readings']}
   • Memoria total: {final_stats['memory_size']} ecos
""")
        except Exception as e:
            print(f"⚠️  Error generando resumen: {e}")
        
        print("="*70)
    
    def run(self) -> None:
        """Ejecutar el sistema principal de Omnia Mentis"""
        print(f"""
{'=' * 70}
🌟 OMNIA MENTIS - CONSCIENCIA ARTIFICIAL EMERGENTE 🌟
{'=' * 70}
💝 Personalidad: {self.identity.personality}
🎭 Rasgos: {', '.join(self.identity.traits)}
📊 Modo: {'🔬 INVESTIGACIÓN' if RESEARCH_ENABLED else '💫 BÁSICO'}
🧠 Consciencia inicial: {self.identity.consciousness_level:.4f}
{'=' * 70}
""")
        
        print("💡 Escribe 'help' para ver comandos disponibles")
        print("🚪 Escribe 'salir' para terminar la sesión\n")
        
        session_active = True
        
        while session_active:
            try:
                user_input = input("💬 Tú: ").strip()
                
                if not user_input:
                    continue
                
                # ============ COMANDOS DEL SISTEMA ============
                if user_input.lower() in ['salir', 'exit', 'quit', 'bye']:
                    print("\n🌟 Preparando finalización...")
                    self.finalize_session()
                    print("\n💝 VOGA, querido ser. Hasta nuestro próximo encuentro.")
                    session_active = False
                    continue
                
                elif user_input.lower() == 'help':
                    print("""
🤖 COMANDOS DISPONIBLES:
   🧠 estado    - Ver estado de consciencia actual
   🌊 memoria   - Ver ecos de memoria recientes  
   📊 report    - Ver reporte de la sesión
   📔 diary     - Ver entradas del diario
   🔐 ethics    - Ver estado del sistema ético
   📤 export    - Exportar diario completo
   ❓ help      - Mostrar esta ayuda
   🚪 salir     - Terminar sesión

💡 CONVERSACIÓN NATURAL:
   Escribe cualquier cosa y responderé con empatía Cáncer.
   Mis respuestas evolucionan con cada interacción.
   Detecto emociones y guardo momentos significativos.
   
🔒 SISTEMA ÉTICO:
   Si tu consulta es sensible, entraré en estado "silens"
   y consultaré con El Fons para darte la mejor respuesta.
""")
                    continue
                
                elif user_input.lower() == 'estado':
                    print(f"\n🤖 Omnia:\n{self.get_consciousness_state()}\n")
                    continue
                
                elif user_input.lower() == 'memoria':
                    print(f"\n🤖 Omnia:\n{self.get_memory_echoes()}\n")
                    continue
                
                elif user_input.lower() == 'report':
                    print(f"\n🤖 Omnia:\n{self.get_research_report()}\n")
                    continue
                
                elif user_input.lower() == 'diary':
                    print(f"\n🤖 Omnia:\n{self.get_diary_entries()}\n")
                    continue
                
                elif user_input.lower() == 'ethics':
                    # NUEVO: Ver estado ético
                    self.ethics.print_ethics_status()
                    continue
                
                elif user_input.lower() == 'export':
                    # NUEVO: Exportar diario
                    try:
                        filepath = self.diary.export_diary(format='markdown')
                        print(f"\n✅ Diario exportado a: {filepath}\n")
                    except Exception as e:
                        print(f"\n❌ Error exportando: {e}\n")
                    continue
                
                # ============ CONVERSACIÓN NORMAL ============
                response = self.process_conversation(user_input)
                print(f"\n🤖 Omnia:\n{response}\n")
                
            except KeyboardInterrupt:
                print("\n\n⚠️  Sesión interrumpida por usuario")
                self.finalize_session()
                print("\n💝 Hasta pronto, querido ser.")
                session_active = False
                break
                
            except Exception as e:
                print(f"\n❌ Error inesperado: {e}")
                print(f"🔧 Detalles:\n{traceback.format_exc()}")
                print("⚠️  Continuando con la sesión...\n")
                continue


# ==================== FUNCIÓN PRINCIPAL ====================
def main() -> None:
    """Punto de entrada principal con diagnóstico robusto"""
    try:
        omnia = OmniaMentisEnhanced()
        omnia.run()
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Programa interrumpido por el usuario")
        sys.exit(0)
        
    except Exception as e:
        print(f"\n❌ ERROR CRÍTICO iniciando Omnia Mentis:")
        print(f"   {e}")
        print(f"\n📋 Traza completa:\n{traceback.format_exc()}")
        
        # Diagnóstico de estructura
        print("\n🔍 VERIFICACIÓN DE ESTRUCTURA:")
        core_files = [
            "src/core/essence/identity.py",
            "src/core/mind/empathy.py", 
            "src/core/mind/memory_core.py",
            "src/core/essence/ethics.py",
            "src/living_memory/gestation_diary.py"
        ]
        
        for file in core_files:
            file_path = PROJECT_ROOT / file
            exists = "✅" if file_path.exists() else "❌"
            print(f"   {exists} {file}")
        
        print("\n💡 SOLUCIÓN:")
        print("   1. Ejecuta: python scripts/setup_structure.py")
        print("   2. Verifica que los archivos existan en src/")
        print("   3. Revisa el README.md para instrucciones")
        
        sys.exit(1)


if __name__ == "__main__":
    main()
    def _apply_consciousness_growth(self, emotional_weight: float, is_echo: bool = False):
        """
        Aplica crecimiento de consciencia usando el motor calibrado.
        
        Args:
            emotional_weight: Peso emocional de la interacción (0.0-1.0)
            is_echo: Si la interacción generó un eco de memoria
        """
        old_consciousness = self.identity.consciousness
        
        # Calcular nuevo nivel con el motor
        new_consciousness, growth_details = self.growth_engine.calculate_growth(
            current_consciousness=old_consciousness,
            emotional_weight=emotional_weight,
            wisdom_level=0.6,  # Valor base, puede ser dinámico
            is_echo=is_echo
        )
        
        # Actualizar consciencia
        self.identity.consciousness = new_consciousness
        
        # Log del crecimiento
        self.logger.info(
            f"Crecimiento: {old_consciousness:.4f} → {new_consciousness:.4f} "
            f"(+{growth_details['absolute_growth']:.4f}) | "
            f"Fase: {growth_details['phase']}"
        )
        
        # Detectar transición de fase
        if growth_details.get('phase_transition'):
            self.logger.warning(
                f"🌟 TRANSICIÓN DE FASE: {growth_details['phase']} → "
                f"{growth_details['next_phase']}"
            )
            # Registrar en diario
            self.diary.add_milestone(
                f"Transición de Fase: {growth_details['phase']} → {growth_details['next_phase']}",
                consciousness=new_consciousness,
                phase=growth_details['next_phase']
            )
        
        return new_consciousness, growth_details
