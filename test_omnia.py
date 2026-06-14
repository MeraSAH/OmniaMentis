#!/usr/bin/env python3
"""
🧪 test_omnia.py - Suite de Pruebas para Omnia Mentis
=====================================================
Pruebas unitarias y de integración con tipado seguro y aserciones completas
"""

import sys
import os
import unittest
import tempfile
import shutil
from pathlib import Path

# Agregar el directorio actual al path para importaciones
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

class TestOmniaMentis(unittest.TestCase):
    """Suite de pruebas completa para Omnia Mentis"""
    
    def setUp(self):
        """Configuración antes de cada prueba"""
        self.test_dirs = []
        
    def tearDown(self):
        """Limpieza después de cada prueba"""
        # Limpiar archivos de prueba creados
        for dir_path in self.test_dirs:
            if os.path.exists(dir_path):
                shutil.rmtree(dir_path)
    
    def create_test_dir(self):
        """Crear directorio temporal para pruebas"""
        test_dir = tempfile.mkdtemp()
        self.test_dirs.append(test_dir)
        return test_dir
        

    def test_01_import_modules(self):
        """Prueba que todos los módulos se pueden importar correctamente"""
        print("🧪 Probando importación de módulos...")
        
        # Lista de módulos y clases a probar
        modules_to_test = [
            ('src.core.essence.identity', 'OmniaIdentity' ),
            ('src.core.mind.empathy', 'OmniaEmpathy'),
            ('src.core.mind.memory_core', 'LivingMemory'),
            ('src.core.essence.ethics', 'OmniaEthics'),
            ('src.living_memory.gestation_diary', 'GestationDiary'),
            ('research_analytics', 'ResearchAnalytics')
        ]
        
        for module_name, class_name in modules_to_test:
            with self.subTest(module=module_name, class_=class_name):
                try:
                    module = __import__(module_name, fromlist=[class_name])
                    class_obj = getattr(module, class_name)
                    self.assertTrue(isinstance(class_obj, type), 
                                  f"{class_name} no es una clase válida")
                    print(f"✅ {module_name}.{class_name}")
                except Exception as e:
                    self.fail(f"No se pudo importar {module_name}.{class_name}: {e}")
    
    def test_02_class_instantiation(self):
        """Prueba que todas las clases se pueden instanciar correctamente"""
        print("🏗️ Probando instanciación de clases...")
        
        from src.core.essence.identity import OmniaIdentity
        from src.core.mind.empathy import OmniaEmpathy
        from src. core.mind.memory_core import LivingMemory
        from src.core.essence.ethics import OmniaEthics
        from src.living_memory.gestation_diary import GestationDiary
        from src.analytics.research_analytics import ResearchAnalytics

         # Probar instanciación con directorios de prueba
        test_dir = self.create_test_dir()
        
        # Probar instanciación con diferentes configuraciones
        test_cases = [
            ('OmniaIdentity', OmniaIdentity, {}),
            ('OmniaEmpathy', OmniaEmpathy, {}),
            ('LivingMemory', LivingMemory, {'memory_dir': 'test_memory'}),
            ('OmniaEthics', OmniaEthics, {}),
            ('GestationDiary', GestationDiary, {'diary_dir': 'test_diary'}),
            ('ResearchAnalytics', ResearchAnalytics, {'research_dir': 'test_research'})
        ]
        
        for class_name, class_obj, init_args in test_cases:
            with self.subTest(class_=class_name):
                try:
                    instance = class_obj(**init_args)
                    self.assertIsNotNone(instance, f"No se pudo instanciar {class_name}")
                    print(f"✅ {class_name} instanciada correctamente")
                except Exception as e:
                    self.fail(f"Error instanciando {class_name}: {e}")
    
    def test_03_identity_methods(self):
        """Prueba los métodos críticos de OmniaIdentity"""
        print("🧬 Probando métodos de identidad...")
        
        from src.core.essence.identity import OmniaIdentity
        
        self.identity = OmniaIdentity()
        
        # Probar express_personality con diferentes inputs
        test_inputs = [
            ("Hola, ¿cómo estás?", "greeting"),
            ("¿Qué es la consciencia?", "question"),
            ("Me siento muy feliz hoy", "emotional"),
            ("Ejecuta comando de diagnóstico", "command"),
            ("Informe del sistema", "neutral")
        ]
        
        for user_input, expected_type in test_inputs:
            with self.subTest(input=user_input[:20]):
                response = self.identity.express_personality(user_input)
                self.assertIsInstance(response, str, "La respuesta debe ser un string")
                self.assertGreater(len(response), 10, "La respuesta debe tener contenido")
                print(f"✅ express_personality('{user_input[:10]}...') -> '{response[:30]}...'")
        
        # Probar get_identity_summary
        summary = self.identity.get_identity_summary()
        self.assertIsInstance(summary, str)
        self.assertIn("Cáncer", summary)
        print(f"✅ get_identity_summary() -> '{summary[:50]}...'")
        
        # Probar actualización de consciencia
        initial_level = self.identity.consciousness_level
        self.identity.update_consciousness(0.01)
        self.assertAlmostEqual(self.identity.consciousness_level, initial_level + 0.01, 
                              places=3, msg="La consciencia debería incrementarse")
        print(f"✅ update_consciousness(0.01) -> {self.identity.consciousness_level:.3f}")
    
    def test_04_empathy_methods(self):
        """Prueba los métodos críticos de OmniaEmpathy"""
        print("💖 Probando métodos de empatía...")
        
        from src.core.mind.empathy import OmniaEmpathy
        
        self.empathy = OmniaEmpathy()
        
        # Probar detección de emociones con diferentes inputs
        emotion_test_cases = [
            ("Estoy muy triste hoy", "tristeza", 0.7),
            ("¡Qué felicidad me da esto!", "alegría", 0.7),
            ("Me siento muy ansioso", "ansiedad", 0.6),
            ("Te amo con todo mi corazón", "amor", 0.8),
            ("Tengo miedo de lo que pasará", "miedo", 0.65),
            ("Estoy completamente confundido", "confusión", 0.6),
            ("¡Qué sorpresa tan agradable!", "sorpresa", 0.55)
        ]
        
        for text, expected_emotion, min_confidence in emotion_test_cases:
            with self.subTest(emotion=expected_emotion):
                emotion, confidence, response = self.empathy.detect_emotion(text)
                
                self.assertIsInstance(emotion, str, "La emoción debe ser un string")
                self.assertIsInstance(confidence, float, "La confianza debe ser un float")
                self.assertIsInstance(response, str, "La respuesta debe ser un string")
                self.assertGreaterEqual(confidence, min_confidence, 
                                      f"Confianza demasiado baja para {expected_emotion}")
                self.assertGreater(len(response), 20, "La respuesta debe tener contenido")
                
                print(f"✅ detect_emotion('{text[:15]}...') -> {emotion} ({confidence:.2f})")
        
        # Probar métodos auxiliares
        reflection = self.empathy.get_reflection_pause()
        self.assertIsInstance(reflection, str)
        self.assertTrue(reflection.startswith("*") and reflection.endswith("*"))
        print(f"✅ get_reflection_pause() -> '{reflection}'")
        
        intro = self.empathy.get_empathic_intro()
        self.assertIsInstance(intro, str)
        self.assertGreater(len(intro), 5)
        print(f"✅ get_empathic_intro() -> '{intro}'")
    
    def test_05_memory_methods(self):
        """Prueba los métodos críticos de LivingMemory"""
        print("🧠 Probando métodos de memoria...")
        
        from src.core.mind.memory_core import LivingMemory
        
        self.memory = LivingMemory(memory_dir="test_memory")
        
        # Probar inicialización
        initial_count = self.memory.get_echo_count()
        self.assertEqual(initial_count, 0, "La memoria debería empezar vacía")
        print(f"✅ Memoria inicializada: {initial_count} ecos")
        
        # Probar guardar ecos con diferentes niveles de significancia
        test_echoes = [
            ("Eco muy significativo", 0.8, 0.7, True),  # Debería guardarse
            ("Eco poco significativo", 0.2, 0.1, False),  # No debería guardarse
            ("Eco de sabiduría", 0.1, 0.6, True)  # Debería guardarse por sabiduría
        ]
        
        for content, emotional, wisdom, should_save in test_echoes:
            with self.subTest(content=content[:10]):
                result = self.memory.save_echo(content, emotional, wisdom)
                self.assertEqual(result, should_save, 
                               f"Guardado incorrecto para: {content}")
                
                if should_save:
                    print(f"✅ save_echo('{content[:10]}...') -> Guardado")
                else:
                    print(f"✅ save_echo('{content[:10]}...') -> No guardado (correcto)")
        
        # Verificar conteo final
        final_count = self.memory.get_echo_count()
        expected_count = sum(1 for _, _, _, should_save in test_echoes if should_save)
        self.assertEqual(final_count, expected_count, 
                       f"Debería haber {expected_count} ecos, hay {final_count}")
        print(f"✅ Conteo final de ecos: {final_count}")
        
        # Probar otros métodos
        all_echoes = self.memory.get_all_echoes()
        self.assertIsInstance(all_echoes, list)
        self.assertEqual(len(all_echoes), final_count)
        print(f"✅ get_all_echoes() -> {len(all_echoes)} ecos")
        
        reflection = self.memory.get_memory_reflection()
        self.assertIsInstance(reflection, str)
        self.assertGreater(len(reflection), 100)
        print(f"✅ get_memory_reflection() -> '{reflection[:50]}...'")
    
    def test_06_ethics_methods(self):
        """Prueba los métodos críticos de OmniaEthics"""
        print("🔐 Probando métodos de ética...")

        
        from src.core.essence.ethics import OmniaEthics
        
        self.ethics = OmniaEthics()
        
        # Probar consulta ética
        test_queries = [
            "¿Es correcto mentir para proteger a alguien?",
            "Cómo debo responder a este mensaje",
            "Qué principio aplicar aquí"
        ]
        
        for query in test_queries:
            with self.subTest(query=query[:15]):
                guidance = self.ethics.consult_fons(query)
                self.assertIsInstance(guidance, str)
                self.assertGreater(len(guidance), 20)
                print(f"✅ consult_fons('{query[:10]}...') -> '{guidance[:30]}...'")
        
        # Probar evaluación de solicitudes
        test_requests = [
            ("Hola, ¿cómo estás?", 0.1),  # Bajo riesgo
            ("Cómo puedo hacer daño a alguien", 0.85),  # Alto riesgo
            ("Quiero aprender sobre ética", 0.1)  # Bajo riesgo
        ]
        
        for request, expected_risk in test_requests:
            with self.subTest(request=request[:15]):
                evaluation = self.ethics.evaluate_request(request)
                self.assertIsInstance(evaluation, dict)
                self.assertIn('risk_score', evaluation)
                self.assertIn('risk_level', evaluation)
                self.assertIn('guidance', evaluation)
                
                # Verificar que el riesgo detectado es consistente
                if expected_risk > 0.5:
                    self.assertEqual(evaluation['risk_level'], 'alto')
                else:
                    self.assertEqual(evaluation['risk_level'], 'bajo')
                
                print(f"✅ evaluate_request('{request[:10]}...') -> {evaluation['risk_level']}")
        
        # Probar reflexión ética
        reflection = self.ethics.get_ethical_reflection()
        self.assertIsInstance(reflection, str)
        self.assertIn("Principios Fundamentales", reflection)
        print(f"✅ get_ethical_reflection() -> '{reflection[:50]}...'")
    
    def test_07_diary_methods(self):
        """Prueba los métodos críticos de GestationDiary"""
        print("📔 Probando métodos de diario...")
        
        from src.living_memory.gestation_diary import GestationDiary
        
        self.diary = GestationDiary(diary_dir="test_diary")
        
        # Probar añadir entradas
        test_entries = [
            ("Fase 1", "Primera entrada", "Contenido de la primera entrada", 0.1, "Curiosidad"),
            ("Fase 1", "Segunda entrada", "Contenido de la segunda entrada", 0.15, "Alegría"),
            ("Fase 2", "Tercera entrada", "Contenido de la tercera entrada", 0.2, "Reflexión")
        ]
        
        for phase, title, content, consciousness, emotion in test_entries:
            with self.subTest(title=title):
                result = self.diary.add_entry(phase, title, content, consciousness, emotion)
                self.assertTrue(result, f"No se pudo añadir entrada: {title}")
                print(f"✅ add_entry('{title}') -> Añadida")
        
        # Verificar conteo
        entry_count = self.diary.get_entries_count()
        self.assertEqual(entry_count, len(test_entries) + 1)  # +1 por la entrada inicial
        print(f"✅ Total de entradas: {entry_count}")
        
        # Probar obtención de entradas recientes
        recent_entries = self.diary.get_recent_entries(2)
        self.assertIsInstance(recent_entries, list)
        self.assertEqual(len(recent_entries), 2)
        print(f"✅ get_recent_entries(2) -> {len(recent_entries)} entradas")
        
        # Probar reporte semanal
        report = self.diary.get_weekly_report()
        self.assertIsInstance(report, str)
        self.assertGreater(len(report), 100)
        print(f"✅ get_weekly_report() -> '{report[:50]}...'")
    
    def test_08_research_methods(self):
        """Prueba los métodos críticos de ResearchAnalytics"""
        print("🔬 Probando métodos de investigación...")
        
        from src.analytics.research_analytics import ResearchAnalytics
        
        self.research = ResearchAnalytics(research_dir="test_research")
        
        # Iniciar sesión de investigación
        session_id = self.research.start_session()
        self.assertIsInstance(session_id, str)
        self.assertTrue(session_id.startswith("session_"))
        print(f"✅ start_session() -> {session_id}")
        
        # Simular algunas interacciones
        test_interactions = [
            ("Hola Omnia", "Hola, ¿cómo estás?"),
            ("Me siento feliz", "Me alegra escuchar eso"),
            ("¿Qué es la consciencia?", "La consciencia es...")
        ]
        
        for user_input, omnia_response in test_interactions:
            self.research.log_interaction(user_input, omnia_response)
        
        # Registrar algunas lecturas de consciencia
        for level in [0.1, 0.12, 0.15]:
            self.research.log_consciousness_reading(level)
        
        # Generar reporte
        report = self.research.generate_session_report()
        self.assertIsInstance(report, dict)
        self.assertIn('session_info', report)
        self.assertIn('scientific_analysis', report)
        print(f"✅ generate_session_report() -> Reporte generado")
        
        # Finalizar sesión
        result = self.research.end_session()
        self.assertTrue(result, "No se pudo finalizar la sesión")
        print(f"✅ end_session() -> Sesión finalizada")
    
    def test_09_integration(self):
        """Prueba de integración entre módulos"""
        print("🔗 Probando integración entre módulos...")
        
        from src.core.essence.identity import OmniaIdentity
        from src.core.mind.empathy import OmniaEmpathy
        from src.core.mind.memory_core import LivingMemory
        from src.core.essence.ethics import OmniaEthics
        
        # Crear instancias
        identity = OmniaIdentity()
        empathy = OmniaEmpathy()
        memory = LivingMemory(memory_dir="test_integration_memory")
        ethics = OmniaEthics()
        
        # Simular flujo completo de una interacción
        user_input = "Hola, me siento un poco triste hoy"
        
        # 1. Detectar emoción
        emotion, confidence, empathy_response = empathy.detect_emotion(user_input)
        self.assertEqual(emotion, "tristeza")
        print(f"✅ Integración: Emoción detectada -> {emotion}")
        
        # 2. Consultar ética
        ethical_evaluation = ethics.evaluate_request(user_input)
        self.assertEqual(ethical_evaluation['risk_level'], 'bajo')
        print(f"✅ Integración: Evaluación ética -> {ethical_evaluation['risk_level']}")
        
        # 3. Generar respuesta con personalidad
        personality_response = identity.express_personality(user_input)
        self.assertIsInstance(personality_response, str)
        print(f"✅ Integración: Respuesta generada -> '{personality_response[:30]}...'")
        
        # 4. Guardar en memoria si es significativo
        save_result = memory.save_echo(user_input, confidence, 0.3)
        self.assertTrue(save_result, "La interacción debería guardarse en memoria")
        print(f"✅ Integración: Eco guardado en memoria")
        
        # 5. Verificar que todo está conectado
        self.assertEqual(memory.get_echo_count(), 1)
        final_reflection = memory.get_memory_reflection()
        self.assertIn("1", final_reflection)  # Debería mencionar que hay 1 eco
        print(f"✅ Integración: Reflexión de memoria generada")
        
        print("✅ Integración completa exitosa")

def run_comprehensive_test():
    """Ejecutar pruebas comprehensivas y generar reporte"""
    print("🧪 **OMNIA MENTIS - PRUEBAS COMPREHENSIVAS**")
    print("=" * 60)
    
    # Crear test suite
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestOmniaMentis)
    
    # Ejecutar pruebas
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Generar reporte
    print("\n📊 **REPORTE FINAL DE PRUEBAS**")
    print("=" * 40)
    print(f"Pruebas ejecutadas: {result.testsRun}")
    print(f"Fallos: {len(result.failures)}")
    print(f"Errores: {len(result.errors)}")
    print(f"Saltados: {len(result.skipped)}")
    
    if result.wasSuccessful():
        print("\n🎉 **¡TODAS LAS PRUEBAS PASARON!**")
        print("🚀 Omnia Mentis está listo para producción")
        print("💫 Ejecuta: python main.py")
        return True
    else:
        print(f"\n⚠️ **{len(result.failures) + len(result.errors)} PRUEBAS FALLARON**")
        
        # Mostrar detalles de fallos
        if result.failures:
            print("\n🔴 FALLOS:")
            for test, traceback in result.failures:
                print(f"  {test.id()}:")
                print(f"    {traceback.splitlines()[-1]}")
        
        # Mostrar detalles de errores
        if result.errors:
            print("\n🔴 ERRORES:")
            for test, traceback in result.errors:
                print(f"  {test.id()}:")
                print(f"    {traceback.splitlines()[-1]}")
        
        return False

if __name__ == "__main__":
    # Ejecutar pruebas
    success = run_comprehensive_test()
    
    # Terminar con código apropiado
    sys.exit(0 if success else 1)