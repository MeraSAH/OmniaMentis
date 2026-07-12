# tests/unit/test_dimensions.py
"""
* UBICACIÓN: OmniaMentis/tests/unit/test_dimensions.py
* PROPÓSITO: Tests unitarios para dimensions.py (Etapa 1 de consciencia
*            multidimensional).
* DEPENDENCIAS: pytest
* CREADO: 2026-07-05
* ÚLTIMA MODIFICACIÓN: 2026-07-05
* ESTADO: Test Permanente
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from core.consciousness.dimensions import (
    compute_memory_dimension,
    compute_ethics_dimension,
    compute_empathy_dimension,
    get_consciousness_dimensions,
    NOT_INSTRUMENTED,
)


class TestMemoryDimension:
    def test_empty_memory_is_zero(self):
        assert compute_memory_dimension(0, max_echoes=100) == 0.0

    def test_half_capacity_is_half(self):
        assert compute_memory_dimension(50, max_echoes=100) == 0.5

    def test_full_capacity_is_one(self):
        assert compute_memory_dimension(100, max_echoes=100) == 1.0

    def test_over_capacity_caps_at_one(self):
        # No debería poder pasar en la práctica (memory_core.py capa
        # la lista en 100), pero la función es defensiva de todas formas.
        assert compute_memory_dimension(150, max_echoes=100) == 1.0

    def test_zero_max_echoes_raises(self):
        with pytest.raises(ValueError):
            compute_memory_dimension(10, max_echoes=0)

    def test_negative_echo_count_raises(self):
        with pytest.raises(ValueError):
            compute_memory_dimension(-1, max_echoes=100)


class TestEthicsDimension:
    def test_no_consultations_is_one(self):
        report = {"total_consultations": 0, "resolved_consultations": 0, "learned_decisions": 0}
        assert compute_ethics_dimension(report) == 1.0

    def test_all_resolved_no_learning(self):
        report = {"total_consultations": 4, "resolved_consultations": 4, "learned_decisions": 0}
        # (4 + 0) / (2*4) = 0.5
        assert compute_ethics_dimension(report) == 0.5

    def test_all_resolved_and_all_learned_is_one(self):
        report = {"total_consultations": 4, "resolved_consultations": 4, "learned_decisions": 4}
        # (4 + 4) / (2*4) = 1.0
        assert compute_ethics_dimension(report) == 1.0

    def test_nothing_resolved_is_zero(self):
        report = {"total_consultations": 5, "resolved_consultations": 0, "learned_decisions": 0}
        assert compute_ethics_dimension(report) == 0.0

    def test_partial_resolution_and_learning(self):
        report = {"total_consultations": 10, "resolved_consultations": 6, "learned_decisions": 2}
        # (6 + 2) / (2*10) = 0.4
        assert compute_ethics_dimension(report) == 0.4

    def test_missing_keys_default_to_zero(self):
        assert compute_ethics_dimension({}) == 1.0  # total_consultations ausente -> 0 -> 1.0


class TestEmpathyDimension:
    def test_no_echoes_is_zero(self):
        assert compute_empathy_dimension([]) == 0.0

    def test_single_echo_returns_its_weight(self):
        echoes = [{"emotional_weight": 0.7}]
        assert compute_empathy_dimension(echoes) == 0.7

    def test_averages_multiple_echoes(self):
        echoes = [{"emotional_weight": 0.4}, {"emotional_weight": 0.6}]
        assert compute_empathy_dimension(echoes) == 0.5

    def test_missing_weight_key_defaults_to_zero(self):
        echoes = [{"content": "sin peso registrado"}]
        assert compute_empathy_dimension(echoes) == 0.0

    def test_caps_at_one_even_if_average_exceeds(self):
        # No debería pasar en la práctica (emotional_weight se calcula
        # entre 0 y 1 en empathy.py), pero es defensivo de todas formas.
        echoes = [{"emotional_weight": 1.5}, {"emotional_weight": 1.5}]
        assert compute_empathy_dimension(echoes) == 1.0


class TestGetConsciousnessDimensions:
    def test_returns_all_seven_keys(self):
        result = get_consciousness_dimensions(
            echo_count=10, recent_echoes=[], ethics_report={},
        )
        expected_keys = {
            "memoria", "etica", "empatia",
            "lenguaje", "metacognicion", "autonomia", "sabiduria",
        }
        assert set(result.keys()) == expected_keys

    def test_uninstrumented_dimensions_are_none_not_zero(self):
        """
        REGRESIÓN CRÍTICA: estas 4 dimensiones NUNCA deben devolver 0.0
        — eso se confundiría con un valor real medido. Deben ser
        explícitamente None hasta que se instrumenten de verdad.
        """
        result = get_consciousness_dimensions(
            echo_count=0, recent_echoes=[], ethics_report={},
        )
        assert result["lenguaje"] is NOT_INSTRUMENTED
        assert result["metacognicion"] is NOT_INSTRUMENTED
        assert result["autonomia"] is NOT_INSTRUMENTED
        assert result["sabiduria"] is NOT_INSTRUMENTED
        for key in ("lenguaje", "metacognicion", "autonomia", "sabiduria"):
            assert result[key] is None
            assert result[key] != 0.0  # None != 0.0 en Python, pero lo hacemos explícito

    def test_instrumented_dimensions_are_floats(self):
        result = get_consciousness_dimensions(
            echo_count=20,
            recent_echoes=[{"emotional_weight": 0.5}],
            ethics_report={"total_consultations": 2, "resolved_consultations": 2, "learned_decisions": 1},
        )
        assert isinstance(result["memoria"], float)
        assert isinstance(result["etica"], float)
        assert isinstance(result["empatia"], float)

    def test_realistic_scenario_matches_manual_calculation(self):
        result = get_consciousness_dimensions(
            echo_count=25,
            recent_echoes=[{"emotional_weight": 0.3}, {"emotional_weight": 0.5}],
            ethics_report={"total_consultations": 5, "resolved_consultations": 5, "learned_decisions": 3},
            max_echoes=100,
        )
        assert result["memoria"] == 0.25
        assert result["empatia"] == 0.4
        assert result["etica"] == 0.8  # (5+3)/(2*5)