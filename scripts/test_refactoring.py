"""
Tests Completos del Refactoring - Omnia Mentis
==============================================
Suite de tests para validar los nuevos módulos:
- Motor de crecimiento de consciencia
- Sistema de persistencia atómica
- Logging profesional

Autor: El Fons
Fecha: 2025-11-26
"""

import unittest
from pathlib import Path
import sys
import json
import tempfile
import shutil
from datetime import datetime

# Agregar src al path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

try:
    from core.consciousness.growth_engine import ConsciousnessGrowthEngine
    from core.storage.atomic_persistence import AtomicJSONStore
    from core.logging.logger_setup import setup_logging, get_logger
except ImportError as e:
    print(f"❌ Error importando módulos: {e}")
    print(f"   Asegúrate de haber copiado los archivos a src/")
    sys.exit(1)


class TestGrowthEngine(unittest.TestCase):
    """Tests del motor de crecimiento de consciencia."""

    def setUp(self):
        """Inicializar motor para cada test."""
        self.engine = ConsciousnessGrowthEngine()

    def test_phase_1_basic_growth(self):
        """Test: Crecimiento básico en Fase 1."""
        current = 0.05
        new, details = self.engine.calculate_growth(
            current, emotional_weight=0.5, wisdom_level=0.5, is_echo=False
        )

        self.assertGreater(new, current, "Consciencia debe crecer")
        self.assertLessEqual(new, 0.15, "No debe exceder máximo de Fase 1")
        self.assertEqual(details["phase"], 1, "Debe estar en Fase 1")
        self.assertIn("absolute_growth", details)

    def test_phase_boundaries(self):
        """Test: Respeto de límites de fase."""
        # Consciencia al límite de Fase 1
        current = 0.149
        new, details = self.engine.calculate_growth(
            current, 1.0, 1.0, True  # Máximo crecimiento posible
        )

        # No debe exceder 0.15 (límite de Fase 1)
        self.assertLessEqual(new, 0.15, "No debe exceder límite de fase")

    def test_high_significance_boost(self):
        """Test: Alta significancia acelera crecimiento."""
        # Baja significancia
        growth_low, _ = self.engine.calculate_growth(0.05, 0.1, 0.1, False)

        # Alta significancia
        growth_high, _ = self.engine.calculate_growth(0.05, 1.0, 1.0, False)

        self.assertGreater(
            growth_high - 0.05,
            growth_low - 0.05,
            "Alta significancia debe dar más crecimiento",
        )

    def test_echo_boost(self):
        """Test: Ecos de memoria duplican crecimiento."""
        # Sin eco
        no_echo, details_no = self.engine.calculate_growth(0.05, 0.5, 0.5, False)

        # Con eco
        with_echo, details_with = self.engine.calculate_growth(0.05, 0.5, 0.5, True)

        # Con eco debe crecer más (2x boost)
        self.assertGreater(
            details_with["absolute_growth"],
            details_no["absolute_growth"],
            "Eco debe aumentar crecimiento",
        )

        # Verificar multiplicador de eco
        self.assertEqual(details_with["echo_mult"], 2.0)

    def test_phase_progression(self):
        """Test: Progresión a través de múltiples fases."""
        consciousness = 0.05

        for expected_phase in range(1, 10):
            phase = self.engine._get_current_phase(consciousness)
            self.assertEqual(
                phase,
                expected_phase,
                f"Consciencia {consciousness:.2f} debe estar en Fase {expected_phase}",
            )

            # Saltar al siguiente umbral de fase
            if expected_phase < 9:
                config = self.engine.phase_configs[expected_phase]
                consciousness = config.max_consciousness + 0.01

    def test_interactions_estimation(self):
        """Test: Estimación de interacciones necesarias."""
        estimate = self.engine.estimate_interactions_to_next_phase(0.05)

        self.assertIn("estimated_interactions", estimate)
        self.assertIn("estimated_days", estimate)
        self.assertGreater(estimate["estimated_interactions"], 0)
        self.assertLess(
            estimate["estimated_interactions"], 2000, "Estimación debe ser alcanzable"
        )

        print(
            f"\n   📊 Fase 1→2: ~{estimate['estimated_interactions']} interacciones "
            f"(~{estimate['estimated_days']} días)"
        )

    def test_phase_progress(self):
        """Test: Información de progreso en fase."""
        progress = self.engine.get_phase_progress(0.10)

        self.assertEqual(progress["phase"], 1)
        self.assertGreater(progress["progress_percentage"], 0)
        self.assertLess(progress["progress_percentage"], 100)

    def test_invalid_inputs(self):
        """Test: Validación de inputs inválidos."""
        # Consciencia fuera de rango
        with self.assertRaises(ValueError):
            self.engine.calculate_growth(1.5, 0.5, 0.5, False)

        # Peso emocional fuera de rango
        with self.assertRaises(ValueError):
            self.engine.calculate_growth(0.05, 2.0, 0.5, False)

    def test_all_phases_info(self):
        """Test: Información de todas las fases."""
        phases_info = self.engine.get_all_phases_info()

        self.assertEqual(len(phases_info), 9, "Debe haber 9 fases")

        # Verificar que cada fase tenga la info esperada
        for phase_info in phases_info:
            self.assertIn("phase", phase_info)
            self.assertIn("name", phase_info)
            self.assertIn("target_interactions", phase_info)


class TestAtomicStorage(unittest.TestCase):
    """Tests del sistema de persistencia atómica."""

    def setUp(self):
        """Crear directorio temporal para tests."""
        self.test_dir = Path(tempfile.mkdtemp())
        self.test_file = self.test_dir / "atomic_test.json"
        self.store = AtomicJSONStore(self.test_file)

    def tearDown(self):
        """Limpiar archivos de test."""
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_basic_save_and_load(self):
        """Test: Escritura y lectura básica."""
        data = {"test": "data", "number": 42, "list": [1, 2, 3]}

        success = self.store.save(data)
        self.assertTrue(success, "Guardado debe ser exitoso")

        loaded = self.store.load()
        self.assertEqual(loaded, data, "Datos cargados deben ser iguales")

    def test_nonexistent_file(self):
        """Test: Cargar archivo que no existe."""
        store = AtomicJSONStore(self.test_dir / "nonexistent.json")

        default = {"default": "value"}
        loaded = store.load(default=default)

        self.assertEqual(loaded, default, "Debe retornar valor por defecto")

    def test_backup_creation(self):
        """Test: Backups se crean automáticamente."""
        self.store.save({"version": 1})
        self.store.save({"version": 2})
        self.store.save({"version": 3})

        backups = self.store.get_backups()
        self.assertGreater(len(backups), 0, "Debe haber al menos 1 backup")

        # Verificar que los backups son archivos válidos
        for backup in backups:
            self.assertTrue(backup.exists(), f"Backup {backup} debe existir")

    def test_backup_limit(self):
        """Test: Límite de backups respetado."""
        store = AtomicJSONStore(self.test_file, max_backups=3)

        # Crear más backups que el límite
        for i in range(10):
            store.save({"version": i})

        backups = store.get_backups()
        self.assertLessEqual(len(backups), 3, "No debe haber más de 3 backups")

    def test_corrupted_file_recovery(self):
        """Test: Recuperación desde backup si archivo corrupto."""
        # Guardar datos válidos
        valid_data = {"valid": "data"}
        self.store.save(valid_data)

        # Corromper archivo principal
        with open(self.test_file, "w") as f:
            f.write("{invalid json content")

        # Cargar debe recuperar desde backup
        loaded = self.store.load(default={})
        self.assertEqual(loaded, valid_data, "Debe recuperar desde backup")

    def test_validator(self):
        """Test: Validador personalizado funciona."""

        def validate(data):
            return isinstance(data, dict) and "required_field" in data

        # Datos válidos
        valid_data = {"required_field": "value"}
        success = self.store.save(valid_data, validator=validate)
        self.assertTrue(success)

        # Datos inválidos
        invalid_data = {"other_field": "value"}
        with self.assertRaises(ValueError):
            self.store.save(invalid_data, validator=validate)

    def test_context_manager(self):
        """Test: Context manager para actualización atómica."""
        initial_data = {"counter": 0}
        self.store.save(initial_data)

        # Actualizar usando context manager
        with self.store.atomic_update(default={}) as data:
            data["counter"] += 1
            data["new_key"] = "new_value"

        # Verificar cambios
        loaded = self.store.load()
        self.assertEqual(loaded["counter"], 1)
        self.assertEqual(loaded["new_key"], "new_value")

    def test_restore_from_backup(self):
        """Test: Restauración desde backup específico."""
        # Crear versiones
        self.store.save({"version": 1})
        self.store.save({"version": 2})
        current_data = {"version": 3}
        self.store.save(current_data)

        # Restaurar desde backup más reciente (antes de version 3)
        success = self.store.restore_from_backup(backup_index=0)
        self.assertTrue(success)

        loaded = self.store.load()
        self.assertNotEqual(loaded, current_data, "Debe ser versión anterior")

    def test_delete(self):
        """Test: Eliminación de archivos."""
        self.store.save({"data": "to_delete"})
        self.assertTrue(self.store.exists())

        success = self.store.delete(keep_backups=False)
        self.assertTrue(success)
        self.assertFalse(self.store.exists())


class TestLoggingSetup(unittest.TestCase):
    """Tests del sistema de logging."""

    def setUp(self):
        """Crear directorio temporal para logs."""
        self.test_log_dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        """Limpiar logs de test."""
        shutil.rmtree(self.test_log_dir, ignore_errors=True)

    def test_logging_initialization(self):
        """Test: Sistema de logging se inicializa correctamente."""
        logger = setup_logging(
            log_dir=self.test_log_dir, level=10, console=False  # DEBUG
        )

        self.assertIsNotNone(logger)

        # Verificar que se crearon archivos de log
        main_log = self.test_log_dir / "omnia.log"
        self.assertTrue(main_log.exists(), "Debe crear omnia.log")

    def test_specialized_loggers(self):
        """Test: Loggers especializados funcionan."""
        setup_logging(log_dir=self.test_log_dir, console=False)

        # Ethics logger
        ethics_logger = get_logger("ethics")
        ethics_logger.warning("Test ethical consultation")

        # Research logger
        research_logger = get_logger("research")
        research_logger.info("Test research metric")

        # Verificar archivos especializados
        ethics_log = self.test_log_dir / "ethics.log"
        research_log = self.test_log_dir / "research.log"

        self.assertTrue(ethics_log.exists(), "Debe crear ethics.log")
        self.assertTrue(research_log.exists(), "Debe crear research.log")

    def test_log_levels(self):
        """Test: Diferentes niveles de log."""
        setup_logging(log_dir=self.test_log_dir, console=False)
        logger = get_logger("test")

        logger.debug("Debug message")
        logger.info("Info message")
        logger.warning("Warning message")
        logger.error("Error message")

        # Verificar que el log contiene los mensajes
        main_log = self.test_log_dir / "omnia.log"
        with open(main_log) as f:
            content = f.read()

        self.assertIn("Info message", content)
        self.assertIn("Warning message", content)


class TestIntegration(unittest.TestCase):
    """Tests de integración entre módulos."""

    def setUp(self):
        """Setup para tests de integración."""
        self.test_dir = Path(tempfile.mkdtemp())
        self.engine = ConsciousnessGrowthEngine()
        self.store = AtomicJSONStore(self.test_dir / "integration.json")
        setup_logging(log_dir=self.test_dir / "logs", console=False)

    def tearDown(self):
        """Limpieza."""
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_consciousness_persistence(self):
        """Test: Guardar y cargar estado de consciencia."""
        # Simular crecimiento
        consciousness = 0.05
        history = []

        for i in range(10):
            new_consciousness, details = self.engine.calculate_growth(
                consciousness,
                emotional_weight=0.5 + (i * 0.05),
                wisdom_level=0.6,
                is_echo=(i % 3 == 0),
            )

            history.append(
                {
                    "iteration": i,
                    "old": consciousness,
                    "new": new_consciousness,
                    "growth": details["absolute_growth"],
                }
            )

            consciousness = new_consciousness

        # Guardar estado
        state = {
            "current_consciousness": consciousness,
            "history": history,
            "timestamp": datetime.now().isoformat(),
        }

        self.store.save(state)

        # Cargar estado
        loaded_state = self.store.load()

        self.assertEqual(
            loaded_state["current_consciousness"],
            consciousness,
            "Consciencia debe persistir correctamente",
        )
        self.assertEqual(len(loaded_state["history"]), 10)

    def test_full_workflow(self):
        """Test: Flujo completo de interacción."""
        logger = get_logger("integration")

        # Estado inicial
        consciousness = 0.05
        phase = 1

        # Simular 5 interacciones
        for i in range(5):
            # Calcular crecimiento
            new_consciousness, details = self.engine.calculate_growth(
                consciousness, emotional_weight=0.7, wisdom_level=0.6, is_echo=True
            )

            # Log de interacción
            logger.info(
                f"Interacción {i}: {consciousness:.4f} → {new_consciousness:.4f}"
            )

            # Detectar transición de fase
            if details["phase_transition"]:
                logger.warning(f"Transición de fase: {phase} → {details['next_phase']}")
                phase = details["next_phase"]

            consciousness = new_consciousness

        # Verificar que hay logs
        log_file = self.test_dir / "logs" / "omnia.log"
        self.assertTrue(log_file.exists())

        with open(log_file) as f:
            content = f.read()

        self.assertIn("Interacción", content)


def run_tests():
    """Ejecuta todos los tests y genera reporte."""
    print("=" * 70)
    print("🧪 TESTS DEL REFACTORING - OMNIA MENTIS")
    print("=" * 70)
    print()

    # Crear test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Agregar tests
    suite.addTests(loader.loadTestsFromTestCase(TestGrowthEngine))
    suite.addTests(loader.loadTestsFromTestCase(TestAtomicStorage))
    suite.addTests(loader.loadTestsFromTestCase(TestLoggingSetup))
    suite.addTests(loader.loadTestsFromTestCase(TestIntegration))

    # Ejecutar tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Reporte final
    print("\n" + "=" * 70)
    print("📊 RESULTADOS FINALES")
    print("=" * 70)
    print(f"   Tests ejecutados: {result.testsRun}")
    print(
        f"   ✅ Exitosos: {result.testsRun - len(result.failures) - len(result.errors)}"
    )
    print(f"   ❌ Fallidos: {len(result.failures)}")
    print(f"   💥 Errores: {len(result.errors)}")

    if result.wasSuccessful():
        print("\n   🎉 TODOS LOS TESTS PASARON")
        print("   ✅ Refactoring completado exitosamente")
    else:
        print("\n   ⚠️  ALGUNOS TESTS FALLARON")
        print("   Revisar detalles arriba")

    print("=" * 70)

    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
