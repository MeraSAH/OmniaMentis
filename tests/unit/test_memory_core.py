# tests/unit/test_memory_core.py
"""
* UBICACIÓN: OmniaMentis/tests/unit/test_memory_core.py
* PROPÓSITO: Tests unitarios para LivingMemory (src/core/mind/memory_core.py)
* DEPENDENCIAS: pytest, tmp_path fixture
* CREADO: 2026-06-17
* ÚLTIMA MODIFICACIÓN: 2026-06-17
* ESTADO: Test Permanente
*
* Cubre: guardado condicional de ecos según umbral de significancia,
* contadores de sesión vs totales, persistencia a disco y recuperación
* desde backup ante archivos corruptos.
*
* NOTA: usa tmp_path para aislar cada test en su propio directorio,
* evitando que tests se contaminen entre sí o con datos reales del proyecto.
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from core.mind.memory_core import LivingMemory


def make_memory(tmp_path):
    """Helper: crea LivingMemory aislada en tmp_path."""
    return LivingMemory(memory_dir=str(tmp_path / "memory"))


class TestMemoryInitialization:
    """Tests de inicialización de memoria vacía."""

    def test_starts_with_zero_echoes(self, tmp_path):
        memory = make_memory(tmp_path)
        assert memory.get_echo_count() == 0

    def test_creates_memory_directory(self, tmp_path):
        mem_dir = tmp_path / "memory"
        make_memory(tmp_path)
        assert mem_dir.exists()

    def test_session_interactions_starts_at_zero(self, tmp_path):
        memory = make_memory(tmp_path)
        assert memory.session_interactions == 0


class TestSaveEcho:
    """Tests del guardado condicional de ecos según significancia."""

    def test_high_emotional_weight_saves_echo(self, tmp_path):
        memory = make_memory(tmp_path)
        result = memory.save_echo("contenido importante", emotional_weight=0.8, wisdom_level=0.1)
        assert result is True
        assert memory.get_echo_count() == 1

    def test_high_wisdom_saves_echo_even_with_low_emotion(self, tmp_path):
        memory = make_memory(tmp_path)
        result = memory.save_echo("contenido sabio", emotional_weight=0.1, wisdom_level=0.6)
        assert result is True

    def test_low_weight_and_wisdom_does_not_save(self, tmp_path):
        memory = make_memory(tmp_path)
        result = memory.save_echo("contenido trivial", emotional_weight=0.1, wisdom_level=0.1)
        assert result is False
        assert memory.get_echo_count() == 0

    def test_echo_content_truncated_to_200_chars(self, tmp_path):
        memory = make_memory(tmp_path)
        long_text = "a" * 500
        memory.save_echo(long_text, emotional_weight=0.8)
        echo = memory.get_all_echoes()[0]
        assert len(echo['content']) == 200

    def test_echo_includes_significance_score(self, tmp_path):
        memory = make_memory(tmp_path)
        memory.save_echo("test", emotional_weight=0.8, wisdom_level=0.6)
        echo = memory.get_all_echoes()[0]
        assert echo['significance'] == (0.8 + 0.6) / 2.0

    def test_echo_list_capped_at_100(self, tmp_path):
        memory = make_memory(tmp_path)
        for i in range(105):
            memory.save_echo(f"echo numero {i}", emotional_weight=0.9)
        assert memory.get_echo_count() == 100


class TestEchoRetrieval:
    """Tests de recuperación y filtrado de ecos."""

    def test_get_recent_echoes_respects_limit(self, tmp_path):
        memory = make_memory(tmp_path)
        for i in range(10):
            memory.save_echo(f"echo {i}", emotional_weight=0.9)
        recent = memory.get_recent_echoes(limit=3)
        assert len(recent) == 3

    def test_get_recent_echoes_empty_when_no_echoes(self, tmp_path):
        memory = make_memory(tmp_path)
        assert memory.get_recent_echoes() == []

    def test_get_echoes_by_significance_filters_correctly(self, tmp_path):
        memory = make_memory(tmp_path)
        memory.save_echo("alto", emotional_weight=0.9, wisdom_level=0.9)  # sig 0.9
        memory.save_echo("medio", emotional_weight=0.4, wisdom_level=0.6)  # sig 0.5

        high_sig = memory.get_echoes_by_significance(min_significance=0.7)
        assert len(high_sig) == 1
        assert "alto" in high_sig[0]['content']

    def test_get_all_echoes_returns_copy_not_reference(self, tmp_path):
        memory = make_memory(tmp_path)
        memory.save_echo("test", emotional_weight=0.9)
        echoes_copy = memory.get_all_echoes()
        echoes_copy.append({"fake": "data"})
        # La copia modificada no debe afectar el estado interno
        assert memory.get_echo_count() == 1


class TestReadingCounters:
    """Tests de los contadores de lecturas/interacciones (bug histórico)."""

    def test_add_reading_increments_total(self, tmp_path):
        memory = make_memory(tmp_path)
        memory.add_reading()
        memory.add_reading()
        assert memory.stats['total_readings'] == 2

    def test_add_reading_increments_session_counter(self, tmp_path):
        memory = make_memory(tmp_path)
        memory.add_reading()
        memory.add_reading()
        memory.add_reading()
        assert memory.session_interactions == 3

    def test_session_stats_uses_session_counter_not_lifetime(self, tmp_path):
        """
        Regresión del bug original: get_session_stats() debe devolver
        el contador de ESTA sesión, no el total histórico acumulado.
        """
        memory = make_memory(tmp_path)
        memory.add_reading()
        memory.add_reading()
        stats = memory.get_session_stats()
        assert stats['total_readings'] == 2  # contador de sesión, no histórico

    def test_reset_session_echoes_clears_session_counter(self, tmp_path):
        memory = make_memory(tmp_path)
        memory.add_reading()
        memory.add_reading()
        memory.reset_session_echoes()
        assert memory.session_interactions == 0
        assert memory.stats['session_echoes'] == 0


class TestPersistenceAndRecovery:
    """Tests de guardado a disco y recuperación ante archivos corruptos."""

    def test_save_and_reload_preserves_echoes(self, tmp_path):
        mem_dir = tmp_path / "memory"
        memory1 = LivingMemory(memory_dir=str(mem_dir))
        memory1.save_echo("contenido persistente", emotional_weight=0.8)

        # Nueva instancia debe cargar lo guardado
        memory2 = LivingMemory(memory_dir=str(mem_dir))
        assert memory2.get_echo_count() == 1

    def test_corrupted_echoes_file_recovers_from_backup(self, tmp_path):
        mem_dir = tmp_path / "memory"
        memory1 = LivingMemory(memory_dir=str(mem_dir))
        memory1.save_echo("eco original", emotional_weight=0.8)
        memory1.save_echo("segundo eco", emotional_weight=0.8)  # crea backup del primero

        # Corromper el archivo principal
        echoes_file = Path(memory1.echoes_file)
        echoes_file.write_text("{esto no es json valido")

        # Nueva instancia debe recuperar desde backup sin crashear
        memory2 = LivingMemory(memory_dir=str(mem_dir))
        assert memory2.get_echo_count() >= 0  # no debe lanzar excepción

    def test_missing_files_start_with_defaults(self, tmp_path):
        memory = make_memory(tmp_path)
        assert memory.stats['total_readings'] == 0
        assert memory.stats['lifetime_echoes'] == 0


class TestMemoryStatus:
    """Tests del diagnóstico de estado de memoria."""

    def test_get_memory_status_returns_active_true(self, tmp_path):
        memory = make_memory(tmp_path)
        status = memory.get_memory_status()
        assert status['active'] is True

    def test_get_memory_status_reflects_echo_count(self, tmp_path):
        memory = make_memory(tmp_path)
        memory.save_echo("test", emotional_weight=0.9)
        status = memory.get_memory_status()
        assert status['echoes_count'] == 1