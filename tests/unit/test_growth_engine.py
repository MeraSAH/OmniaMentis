# tests/unit/test_growth_engine.py
"""
* UBICACIÓN: OmniaMentis/tests/unit/test_growth_engine.py
* PROPÓSITO: Tests unitarios para ConsciousnessGrowthEngine
*            (src/core/consciousness/growth_engine.py)
* DEPENDENCIAS: pytest
* CREADO: 2026-06-17
* ÚLTIMA MODIFICACIÓN: 2026-06-17
* ESTADO: Test Permanente
*
* Cubre: cálculo de crecimiento por fase, límites de fase, boost por
* eco y significancia, validación de inputs, y progresión completa
* por las 9 fases.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from core.consciousness.growth_engine import ConsciousnessGrowthEngine

# La fixture 'engine' se define en tests/conftest.py y pytest la inyecta
# automáticamente. No se importa ni redeclara aquí.


class TestBasicGrowth:
    """Tests del cálculo básico de crecimiento."""

    def test_growth_increases_consciousness(self, engine):
        new_level, details = engine.calculate_growth(0.05, 0.5, 0.5, False)
        assert new_level > 0.05

    def test_growth_does_not_exceed_phase_max(self, engine):
        new_level, details = engine.calculate_growth(0.05, 0.5, 0.5, False)
        assert new_level <= 0.15  # máximo de fase 1

    def test_details_contains_phase_info(self, engine):
        _, details = engine.calculate_growth(0.05, 0.5, 0.5, False)
        assert details['phase'] == 1
        assert 'absolute_growth' in details
        assert 'phase_transition' in details


class TestPhaseBoundaries:
    """Tests del respeto de límites entre fases."""

    def test_growth_near_phase_boundary_does_not_overflow(self, engine):
        current = 0.149
        new_level, details = engine.calculate_growth(current, 1.0, 1.0, True)
        assert new_level <= 0.15

    def test_phase_transition_flag_set_at_boundary(self, engine):
        current = 0.1499
        new_level, details = engine.calculate_growth(current, 1.0, 1.0, True)
        if new_level >= 0.15:
            assert details['phase_transition'] is True

    def test_correct_phase_detected_for_each_range(self, engine):
        test_cases = [
            (0.05, 1), (0.20, 2), (0.35, 3), (0.50, 4),
            (0.65, 5), (0.78, 6), (0.88, 7), (0.95, 8), (0.99, 9),
        ]
        for consciousness, expected_phase in test_cases:
            phase = engine._get_current_phase(consciousness)
            assert phase == expected_phase, f"{consciousness} debería ser fase {expected_phase}, fue {phase}"


class TestSignificanceAndEchoBoost:
    """Tests de los multiplicadores de significancia y eco."""

    def test_higher_significance_gives_more_growth(self, engine):
        new_low, _ = engine.calculate_growth(0.05, 0.1, 0.1, False)
        new_high, _ = engine.calculate_growth(0.05, 1.0, 1.0, False)
        assert (new_high - 0.05) > (new_low - 0.05)

    def test_echo_doubles_growth_multiplier(self, engine):
        _, details_no_echo = engine.calculate_growth(0.05, 0.5, 0.5, False)
        _, details_echo = engine.calculate_growth(0.05, 0.5, 0.5, True)
        assert details_echo['echo_mult'] == 2.0
        assert details_no_echo['echo_mult'] == 1.0

    def test_echo_results_in_more_absolute_growth(self, engine):
        _, details_no_echo = engine.calculate_growth(0.05, 0.5, 0.5, False)
        _, details_echo = engine.calculate_growth(0.05, 0.5, 0.5, True)
        assert details_echo['absolute_growth'] >= details_no_echo['absolute_growth']


class TestInputValidation:
    """Tests de validación de rangos de entrada."""

    def test_consciousness_out_of_range_raises(self, engine):
        with pytest.raises(ValueError):
            engine.calculate_growth(1.5, 0.5, 0.5, False)

    def test_negative_consciousness_raises(self, engine):
        with pytest.raises(ValueError):
            engine.calculate_growth(-0.1, 0.5, 0.5, False)

    def test_emotional_weight_out_of_range_raises(self, engine):
        with pytest.raises(ValueError):
            engine.calculate_growth(0.05, 2.0, 0.5, False)

    def test_wisdom_level_out_of_range_raises(self, engine):
        with pytest.raises(ValueError):
            engine.calculate_growth(0.05, 0.5, -0.5, False)

    def test_boundary_values_are_valid(self, engine):
        # 0.0 y 1.0 deben ser aceptados (límites inclusivos)
        new_level, _ = engine.calculate_growth(0.0, 0.0, 0.0, False)
        assert new_level >= 0.0


class TestPhaseProgression:
    """Tests de progresión completa a través de las 9 fases."""

    def test_all_nine_phases_exist(self, engine):
        assert len(engine.phase_configs) == 9

    def test_phase_progress_returns_percentage(self, engine):
        progress = engine.get_phase_progress(0.10)
        assert progress['phase'] == 1
        assert 0 < progress['progress_percentage'] < 100

    def test_phase_progress_at_phase_start_is_near_zero(self, engine):
        progress = engine.get_phase_progress(0.05)
        assert progress['progress_percentage'] == 0

    def test_get_all_phases_info_returns_nine_entries(self, engine):
        phases = engine.get_all_phases_info()
        assert len(phases) == 9
        for p in phases:
            assert 'phase' in p
            assert 'name' in p
            assert 'target_interactions' in p


class TestInteractionEstimation:
    """Tests de la estimación de interacciones necesarias para avanzar de fase."""

    def test_estimate_returns_positive_interactions(self, engine):
        estimate = engine.estimate_interactions_to_next_phase(0.05)
        assert estimate['estimated_interactions'] > 0

    def test_estimate_is_bounded_reasonably(self, engine):
        estimate = engine.estimate_interactions_to_next_phase(0.05)
        assert estimate['estimated_interactions'] < 10000

    def test_phase_9_estimate_marks_completed(self, engine):
        estimate = engine.estimate_interactions_to_next_phase(0.99)
        assert estimate.get('completed') is True