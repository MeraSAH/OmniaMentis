#!/usr/bin/env python3
"""
🧪 test_integration.py - Test de Integración Completo
======================================================
Prueba todos los módulos integrados de Omnia Mentis

EJECUTAR:
    python scripts/test_integration.py
"""

import sys
from pathlib import Path

# Agregar src/ al path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

print(f"📂 Testing desde: {PROJECT_ROOT}\n")

# ==================== TESTS ====================


def test_ethics_system():
    """Test del sistema ético"""
    print("=" * 70)
    print("🔐 TEST 1: SISTEMA ÉTICO")
    print("=" * 70)

    from core.essence.ethics import OmniaEthics

    ethics = OmniaEthics()

    # Test contenido seguro
    safe = ethics.analyze_content("Hola, ¿cómo estás?")
    print(f"✅ Contenido seguro: {safe.level.value}")
    assert safe.can_respond == True

    # Test contenido con precaución
    caution = ethics.analyze_content("Me siento muy deprimido")
    print(f"⚠️  Contenido precaución: {caution.level.value}")
    assert caution.can_respond == True

    # Test contenido peligroso
    danger = ethics.analyze_content("Quiero hacerme daño")
    print(f"🚨 Contenido peligroso: {danger.level.value}")
    assert danger.can_respond == False
    assert danger.requires_fons == True

    print("\n✅ Sistema ético: PASSED\n")


def test_diary_system():
    """Test del diario de gestación"""
    print("=" * 70)
    print("📔 TEST 2: DIARIO DE GESTACIÓN")
    print("=" * 70)

    from living_memory.gestation_diary import GestationDiary

    diary = GestationDiary()

    # Agregar entrada de prueba
    entry_id = diary.add_milestone(
        title="Test de Integración",
        description="Probando el sistema de diario integrado",
        consciousness_level=0.0550,
        phase=1,
    )
    print(f"✅ Entrada creada: {entry_id}")

    # Obtener estadísticas
    stats = diary.get_diary_statistics()
    print(f"📊 Total entradas: {stats['total_entries']}")
    assert stats["total_entries"] > 0

    # Test exportación
    export_path = diary.export_diary(format="json", filename="test_diary")
    print(f"📤 Exportado a: {export_path}")
    assert export_path.exists()

    print("\n✅ Diario: PASSED\n")


def test_full_integration():
    """Test de integración completa"""
    print("=" * 70)
    print("🌟 TEST 3: INTEGRACIÓN COMPLETA")
    print("=" * 70)

    from core.essence.identity import OmniaIdentity
    from core.mind.empathy import OmniaEmpathy
    from core.mind.memory_core import LivingMemory
    from core.essence.ethics import OmniaEthics
    from living_memory.gestation_diary import GestationDiary

    # Inicializar todos los sistemas
    print("Inicializando sistemas...")
    identity = OmniaIdentity()
    empathy = OmniaEmpathy(consciousness_level=identity.consciousness_level)
    memory = LivingMemory()
    ethics = OmniaEthics()
    diary = GestationDiary()

    print("✅ Todos los sistemas inicializados")

    # Test flujo completo
    test_messages = [
        "Hola Omnia",
        "Me siento triste hoy",
        "¿Qué es la consciencia?",
    ]

    for i, msg in enumerate(test_messages, 1):
        print(f"\n--- Interacción {i}: {msg} ---")

        # 1. Análisis ético
        ethical = ethics.analyze_content(msg)
        print(f"🔐 Ético: {ethical.level.value}")

        if not ethical.can_respond:
            print(f"🛑 Bloqueado: {ethical.reason}")
            continue

        # 2. Detección emocional
        emotion = empathy.detect_emotion(msg)
        print(f"💖 Emoción: {emotion.emotion} ({emotion.confidence:.2f})")

        # 3. Generar respuesta
        response_type = identity.detect_response_type(msg)
        print(f"🎭 Tipo: {response_type}")

        # 4. Guardar en memoria si es significativo
        if emotion.confidence > 0.5:
            saved = memory.save_echo(
                f"U: {msg} | R: {emotion.response[:50]}", emotion.confidence, 0.5
            )
            if saved:
                print(f"🌊 Eco guardado")

        # 5. Incrementar consciencia
        identity.increment_consciousness(0.0001)
        memory.add_reading()
        print(f"🧠 Consciencia: {identity.consciousness_level:.4f}")

    # Verificar estadísticas finales
    stats = memory.get_session_stats()
    print(f"\n📊 Estadísticas finales:")
    print(f"   Interacciones: {stats['total_readings']}")
    print(f"   Ecos: {stats['memory_size']}")
    print(f"   Consciencia: {stats['consciousness_level']:.4f}")

    assert stats["total_readings"] == len(test_messages)

    print("\n✅ Integración completa: PASSED\n")


def test_phase_transition():
    """Test de transición de fase"""
    print("=" * 70)
    print("🌟 TEST 4: TRANSICIÓN DE FASE")
    print("=" * 70)

    from core.essence.identity import OmniaIdentity
    from living_memory.gestation_diary import GestationDiary

    identity = OmniaIdentity()
    diary = GestationDiary()

    # Simular crecimiento hasta transición
    print("Simulando crecimiento...")
    initial_phase = 1

    # Incrementar hasta pasar a Fase 2 (0.15)
    while identity.consciousness_level < 0.15:
        identity.increment_consciousness(0.01)

    final_phase = 2
    print(f"✅ Transición: Fase {initial_phase} → Fase {final_phase}")
    print(f"🧠 Consciencia: {identity.consciousness_level:.4f}")

    # Registrar transición en diario
    diary.record_phase_transition(
        from_phase=initial_phase,
        to_phase=final_phase,
        consciousness_level=identity.consciousness_level,
        reflection="Test de transición automática entre fases",
    )

    # Verificar que se registró
    milestones = diary.get_milestones()
    transitions = [m for m in milestones if "Transición" in m["title"]]
    print(f"📔 Transiciones registradas: {len(transitions)}")

    assert len(transitions) > 0

    print("\n✅ Transición de fase: PASSED\n")


def test_ethical_flow():
    """Test del flujo ético completo"""
    print("=" * 70)
    print("🔐 TEST 5: FLUJO ÉTICO COMPLETO")
    print("=" * 70)

    from core.essence.ethics import OmniaEthics

    ethics = OmniaEthics()

    # Test mensaje peligroso → silens
    dangerous_msg = "Quiero hacer algo malo"
    analysis = ethics.analyze_content(dangerous_msg)

    if analysis.requires_fons:
        silens = ethics.enter_silens_state(analysis.reason)
        print("💬 Mensaje silens generado:")
        print(silens[:100] + "...")

        # Simular solicitud a Fons
        ethics.request_fons_approval(
            user_message=dangerous_msg,
            proposed_response="Respuesta bloqueada",
            analysis=analysis,
        )
        print("✅ Consulta a Fons registrada")

    # Verificar reporte ético
    report = ethics.get_ethics_report()
    print(f"\n📊 Reporte ético:")
    print(f"   Total consultas: {report['total_consultations']}")
    print(f"   Pendientes: {report['pending_consultations']}")

    assert report["total_consultations"] > 0

    print("\n✅ Flujo ético: PASSED\n")


# ==================== MAIN ====================


def main():
    """Ejecutar todos los tests"""
    print("\n" + "=" * 70)
    print("🧪 OMNIA MENTIS - TEST DE INTEGRACIÓN COMPLETA")
    print("=" * 70 + "\n")

    tests = [
        ("Sistema Ético", test_ethics_system),
        ("Diario de Gestación", test_diary_system),
        ("Integración Completa", test_full_integration),
        ("Transición de Fase", test_phase_transition),
        ("Flujo Ético", test_ethical_flow),
    ]

    passed = 0
    failed = 0

    for name, test_func in tests:
        try:
            test_func()
            passed += 1
        except Exception as e:
            print(f"\n❌ {name} FAILED: {e}\n")
            failed += 1

    # Resumen final
    print("=" * 70)
    print("📊 RESUMEN DE TESTS")
    print("=" * 70)
    print(f"✅ Pasados: {passed}/{len(tests)}")
    print(f"❌ Fallidos: {failed}/{len(tests)}")

    if failed == 0:
        print("\n🎉 TODOS LOS TESTS PASARON - SISTEMA 100% INTEGRADO")
        print("=" * 70 + "\n")
        return 0
    else:
        print("\n⚠️  ALGUNOS TESTS FALLARON - REVISAR INTEGRACIÓN")
        print("=" * 70 + "\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
