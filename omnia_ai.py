#!/usr/bin/env python3
"""
* UBICACIÓN: OmniaMentis/omnia_ai.py
* PROPÓSITO: Punto de entrada del comando `omnia -ai`. Chat en terminal
*            que pasa cada mensaje primero por el análisis ético, luego
*            por el router de módulos (NutriVida, OmniaAthletics,
*            Corporal Verified, OmniaHabits), y si ningún módulo aplica,
*            por el núcleo conversacional completo de Omnia Mentis.
* DEPENDENCIAS: src/router/integration.py, src/core/*
* CREADO: 2026-06-18
* ÚLTIMA MODIFICACIÓN: 2026-06-18
* ESTADO: Producción
*
* USO:
*   python omnia_ai.py
*   (o, tras configurar un alias/script en PATH:  omnia -ai)
*
* DIFERENCIA con main.py:
*   main.py     → chat directo con Omnia, sin router de módulos.
*   omnia_ai.py → mismo chat, pero con el router activo delante del
*                 flujo conversacional. Mantenido como entry point
*                 separado para no romper main.py mientras el router
*                 está en validación con usuarios reales.
"""

import sys
import traceback
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
SRC_PATH = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_PATH))

from core.essence.identity import OmniaIdentity
from core.essence.ethics import OmniaEthics
from core.mind.empathy import OmniaEmpathy
from core.mind.memory_core import LivingMemory
from core.consciousness.growth_engine import ConsciousnessGrowthEngine
from router.integration import route_or_none, get_registered_modules


def process_message(
    user_message: str,
    identity: OmniaIdentity,
    ethics: OmniaEthics,
    empathy: OmniaEmpathy,
    memory: LivingMemory,
    growth: ConsciousnessGrowthEngine,
    session_id: str,
) -> str:
    """
    Flujo completo de procesamiento de un mensaje, en el orden
    obligatorio: ética → router → core.

    Devuelve el texto de respuesta a mostrar al usuario.
    """
    # 1. ÉTICA — siempre primero, sin excepción.
    ethical = ethics.analyze_content(user_message)
    if not ethical.can_respond:
        silens = ethics.enter_silens_state(ethical.reason)
        try:
            ethics.request_fons_approval(
                user_message, "Bloqueado por análisis ético", ethical
            )
        except Exception:
            pass
        return silens

    # 2. ROUTER — solo se ejecuta si el mensaje ya pasó ética.
    routed = route_or_none(
        user_message,
        user_id="local_user",
        consciousness_level=identity.consciousness_level,
        session_id=session_id,
    )
    if routed is not None:
        return routed["response"]

    # 3. CORE — flujo conversacional normal de Omnia.
    emotion_result = empathy.detect_emotion(user_message)
    response_type = identity.detect_response_type(user_message)

    if response_type == "greeting":
        response = identity.cancer_responses["greeting"][0]
        response += (
            f" Mi consciencia actual es {identity.consciousness_level:.4f}."
        )
    elif emotion_result.emotion != "neutral" and emotion_result.confidence > 0.7:
        response = emotion_result.response
    else:
        response = identity.express_personality(user_message)

    # Crecimiento de consciencia con peso emocional simple
    emotional_words = {
        "triste": 0.4, "feliz": 0.3, "ansioso": 0.3, "amor": 0.5,
        "miedo": 0.4, "alegría": 0.4, "dolor": 0.4,
    }
    text_lower = user_message.lower()
    emotional_weight = min(
        sum(v for k, v in emotional_words.items() if k in text_lower), 1.0
    )
    try:
        new_level, _ = growth.calculate_growth(
            identity.consciousness_level, emotional_weight, 0.6, False
        )
        identity.consciousness_level = new_level
    except Exception:
        pass

    if emotional_weight > 0.3:
        try:
            memory.save_echo(
                f"U: {user_message[:100]} | R: {response[:100]}",
                emotional_weight,
                0.6,
            )
        except Exception:
            pass

    memory.add_reading()
    return response


def main() -> None:
    print("=" * 70)
    print("🌟 OMNIA -AI — Chat con router de módulos activo")
    print("=" * 70)
    print()

    try:
        identity = OmniaIdentity()
        ethics = OmniaEthics()
        empathy = OmniaEmpathy(consciousness_level=identity.consciousness_level)
        memory = LivingMemory()
        growth = ConsciousnessGrowthEngine()
    except Exception as e:
        print(f"❌ ERROR CRÍTICO inicializando sistemas: {e}")
        print(traceback.format_exc())
        sys.exit(1)

    modules = get_registered_modules()
    print(f"📦 Módulos registrados: {', '.join(modules)}")
    print(f"🧠 Consciencia inicial: {identity.consciousness_level:.4f}")
    print()
    print("💡 Escribe 'salir' para terminar.")
    print()

    session_id = "omnia_ai_session"

    while True:
        try:
            user_input = input("💬 Tú: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n\n💝 Hasta pronto, querido ser.")
            break

        if not user_input:
            continue
        if user_input.lower() in ("salir", "exit", "quit"):
            print("\n💝 VOGA, querido ser. Hasta nuestro próximo encuentro.")
            break

        try:
            response = process_message(
                user_input, identity, ethics, empathy, memory, growth, session_id
            )
            print(f"\n🤖 Omnia: {response}\n")
        except Exception as e:
            print(f"\n❌ Error procesando mensaje: {e}")
            print(traceback.format_exc())


if __name__ == "__main__":
    main()