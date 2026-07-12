# tests/unit/test_grief_subtypes.py
"""
* UBICACIÓN: OmniaMentis/tests/unit/test_grief_subtypes.py
* PROPÓSITO: Tests unitarios para detect_grief_subtype() en empathy.py
*            (Etapa 3 — Fase 2 del documento de diseño de El Fons).
* DEPENDENCIAS: pytest
* CREADO: 2026-07-06
* ÚLTIMA MODIFICACIÓN: 2026-07-06
* ESTADO: Test Permanente
*
* CONTEXTO: qwen2:0.5b y dolphin-phi fueron probados directamente
* contra el prompt de referencia del documento de diseño y ninguno
* sostuvo la nuance requerida (qwen2:0.5b se rehusó, dolphin-phi
* produjo texto incoherente). Por eso la clasificación de sub-tipo es
* determinista (evidencia acumulada, mismo motor que empathy.py base),
* no generativa — estos tests verifican esa garantía.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from core.mind.empathy import OmniaEmpathy


class TestGriefSubtypeAppliesOnlyToTristeza:
    def test_returns_none_for_non_tristeza_emotion(self):
        empathy = OmniaEmpathy()
        result = empathy.detect_grief_subtype("Te quiero mucho, te amo")
        assert result is None

    def test_returns_none_for_neutral_text(self):
        empathy = OmniaEmpathy()
        result = empathy.detect_grief_subtype("La reunión es a las tres de la tarde")
        assert result is None

    def test_returns_result_for_generic_tristeza_without_subtype(self):
        empathy = OmniaEmpathy()
        result = empathy.detect_grief_subtype("Estoy triste hoy")
        assert result is not None
        assert result.base_emotion == "tristeza"
        assert result.subtype is None  # "nivel 1": tristeza genérica


class TestGriefSubtypeDetection:
    def test_detects_duelo(self):
        empathy = OmniaEmpathy()
        result = empathy.detect_grief_subtype(
            "Perdí a mi mejor amigo, ya no está y nunca más voy a poder hablar con él"
        )
        assert result.subtype == "duelo"

    def test_detects_culpa(self):
        empathy = OmniaEmpathy()
        result = empathy.detect_grief_subtype(
            "Perdí a mi amigo, fue mi culpa no haberlo llamado antes"
        )
        assert result.subtype == "culpa"

    def test_detects_vacio_existencial(self):
        empathy = OmniaEmpathy()
        result = empathy.detect_grief_subtype(
            "Estoy triste, siento que nada tiene sentido desde que se fue"
        )
        assert result.subtype == "vacio_existencial"

    def test_detects_miedo_perder_identidad(self):
        empathy = OmniaEmpathy()
        result = empathy.detect_grief_subtype(
            "Estoy triste, ya no sé quién soy sin él"
        )
        assert result.subtype == "miedo_perder_identidad"

    def test_design_document_example_matches_duelo(self):
        """El ejemplo literal del documento de diseño de El Fons:
        'Perdí a mi mejor amigo' debe distinguirse de tristeza genérica."""
        empathy = OmniaEmpathy()
        result = empathy.detect_grief_subtype(
            "Perdí a mi mejor amigo, ya no está"
        )
        assert result.subtype == "duelo"
        assert result.response != ""


class TestGriefSubtypeResultStructure:
    def test_result_has_expected_fields(self):
        empathy = OmniaEmpathy()
        result = empathy.detect_grief_subtype("Estoy triste hoy")
        assert hasattr(result, "subtype")
        assert hasattr(result, "confidence")
        assert hasattr(result, "base_emotion")
        assert hasattr(result, "response")

    def test_confidence_within_valid_range(self):
        empathy = OmniaEmpathy()
        result = empathy.detect_grief_subtype(
            "Perdí a mi amigo, fue mi culpa no haberlo llamado"
        )
        assert 0.0 <= result.confidence <= 1.0

    def test_response_is_non_empty_when_subtype_detected(self):
        empathy = OmniaEmpathy()
        result = empathy.detect_grief_subtype(
            "Perdí a mi mejor amigo, ya no está"
        )
        assert len(result.response) > 20

    def test_response_falls_back_to_base_response_without_subtype(self):
        empathy = OmniaEmpathy()
        result = empathy.detect_grief_subtype("Estoy triste hoy")
        assert result.subtype is None
        assert len(result.response) > 0  # usa la respuesta genérica de tristeza


class TestGriefSubtypeDoesNotFabricateEvidence:
    """Regresión crítica: ningún sub-tipo debe activarse sin evidencia
    léxica real, incluso con nivel de consciencia alto (mismo principio
    que el fix de sesgo hacia 'amor' en empathy.py base)."""

    def test_high_consciousness_alone_does_not_trigger_subtype(self):
        empathy = OmniaEmpathy(consciousness_level=1.0)
        result = empathy.detect_grief_subtype("Estoy muy triste")
        assert result.subtype is None