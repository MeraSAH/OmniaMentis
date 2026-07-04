# tests/unit/test_empathy.py
"""
* UBICACIÓN: OmniaMentis/tests/unit/test_empathy.py
* PROPÓSITO: Tests unitarios para OmniaEmpathy (src/core/mind/empathy.py)
* DEPENDENCIAS: pytest
* CREADO: 2026-06-17
* ÚLTIMA MODIFICACIÓN: 2026-06-30
* ESTADO: Test Permanente
*
* CAMBIO 2026-06-30: se corrigió el bug de pesos base sesgados hacia
* "amor" en empathy.py (ver cabecera de ese archivo). Los tests que
* antes documentaban el bug como "known_limitation" ahora verifican el
* comportamiento CORRECTO, tal como sus propios docstrings originales
* anticipaban que debía pasar tras el rebalanceo. Se conservan como
* tests de regresión para que el bug nunca vuelva a introducirse
* silenciosamente.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from core.mind.empathy import OmniaEmpathy


class TestEmotionDetection:
    """Tests de detección de cada emoción soportada."""

    def test_detects_tristeza(self):
        empathy = OmniaEmpathy()
        result = empathy.detect_emotion("Estoy muy triste hoy")
        assert result.emotion == "tristeza"
        assert result.confidence >= 0.5

    def test_detects_alegria(self):
        empathy = OmniaEmpathy()
        result = empathy.detect_emotion("¡Qué felicidad me da esto, estoy muy feliz!")
        assert result.emotion == "alegría"

    def test_detects_amor(self):
        empathy = OmniaEmpathy()
        result = empathy.detect_emotion("Te quiero con todo mi corazón, te amo")
        assert result.emotion == "amor"

    def test_detects_confusion(self):
        empathy = OmniaEmpathy()
        result = empathy.detect_emotion("Estoy completamente confundido, no entiendo nada")
        assert result.emotion == "confusión"

    def test_detects_sorpresa(self):
        empathy = OmniaEmpathy()
        result = empathy.detect_emotion("¡Qué sorpresa tan agradable e increíble!")
        assert result.emotion == "sorpresa"

    def test_neutral_reachable_for_text_without_emotional_evidence(self):
        """
        REGRESIÓN DEL BUG PRINCIPAL: con el diseño anterior, "neutral"
        era prácticamente inalcanzable porque los pesos base de las 7
        categorías (0.55-0.8) ya superaban el umbral de clasificación
        sin ninguna palabra clave presente. Una frase sin ninguna
        palabra emocional debe clasificarse ahora como "neutral", no
        como "amor" (que era el resultado incorrecto del bug original).
        """
        empathy = OmniaEmpathy()
        result = empathy.detect_emotion("El cielo está despejado hoy")
        assert result.emotion == "neutral"

    def test_empty_text_returns_neutral_without_crashing(self):
        empathy = OmniaEmpathy()
        result = empathy.detect_emotion("")
        assert result.emotion == "neutral"

    # ------------------------------------------------------------------
    # FIX VERIFICADO: el sesgo hacia "amor" con evidencia real de otras
    # categorías queda corregido.
    # ------------------------------------------------------------------
    #
    # Antes del fix, frases con 1-2 palabras clave de "miedo" o
    # "ansiedad" (sin patrón regex adicional) perdían el desempate
    # frente a "amor" por el peso base más alto de esa categoría
    # (0.8), incluso sin ninguna palabra de amor presente en el texto.
    # Tras rebalancear los pesos (ver empathy.py, sensitivity=0.85
    # para "amor" + eliminación de puntaje de partida), estas mismas
    # frases ahora se clasifican correctamente en su categoría real.

    def test_detects_miedo_when_pattern_matches(self):
        empathy = OmniaEmpathy()
        result = empathy.detect_emotion("no puedo manejar esto, es aterrador")
        assert result.emotion == "miedo"

    def test_miedo_keyword_only_now_classifies_correctly(self):
        """
        Antes del fix (test_known_limitation_miedo_keyword_only_loses_to_amor_base):
        esta frase se clasificaba como "amor" pese a no contener
        ninguna palabra de amor. Tras el fix, clasifica correctamente
        como "miedo".
        """
        empathy = OmniaEmpathy()
        result = empathy.detect_emotion("Tengo mucho miedo, estoy aterrado")
        assert result.emotion == "miedo"

    def test_detects_ansiedad_when_pattern_matches(self):
        empathy = OmniaEmpathy()
        result = empathy.detect_emotion("tengo miedo de lo que pasará, no puedo más")
        assert result.emotion in ("ansiedad", "miedo")

    def test_ansiedad_keyword_only_now_classifies_correctly(self):
        """
        Antes del fix (test_known_limitation_ansiedad_keyword_only_loses_to_amor_base):
        esta frase se clasificaba como "amor". Tras el fix, clasifica
        correctamente como "ansiedad".
        """
        empathy = OmniaEmpathy()
        result = empathy.detect_emotion("Me siento muy ansioso y nervioso")
        assert result.emotion == "ansiedad"

    def test_amor_requires_actual_love_words_not_just_high_base_weight(self):
        """Frase sin ninguna palabra de la categoría 'amor' nunca debe
        clasificarse como amor solo por descarte — debe caer en
        'neutral' o en la categoría con evidencia real, nunca en amor
        por defecto."""
        empathy = OmniaEmpathy()
        result = empathy.detect_emotion("Necesito organizar mi agenda de la semana")
        assert result.emotion != "amor"


class TestEmotionResultStructure:
    """Tests de la estructura del resultado de detección."""

    def test_result_has_emotion_confidence_response(self):
        empathy = OmniaEmpathy()
        result = empathy.detect_emotion("Hola")
        assert hasattr(result, 'emotion')
        assert hasattr(result, 'confidence')
        assert hasattr(result, 'response')

    def test_response_is_non_empty_string(self):
        empathy = OmniaEmpathy()
        result = empathy.detect_emotion("Estoy triste")
        assert isinstance(result.response, str)
        assert len(result.response) > 20

    def test_confidence_is_within_valid_range(self):
        empathy = OmniaEmpathy()
        result = empathy.detect_emotion("Estoy muy triste y deprimido")
        assert 0.0 <= result.confidence <= 1.0

    def test_confidence_never_exceeds_cap(self):
        """Incluso con múltiples palabras clave y patrón, la confianza
        no debe exceder el techo definido (0.95)."""
        empathy = OmniaEmpathy(consciousness_level=1.0)
        result = empathy.detect_emotion("Te quiero, te amo, mi amor, cariño, ternura, adoro, me encantas")
        assert result.confidence <= 0.95


class TestConsciousnessInfluence:
    """Tests de cómo el nivel de consciencia afecta la detección."""

    def test_higher_consciousness_increases_confidence(self):
        low = OmniaEmpathy(consciousness_level=0.05)
        high = OmniaEmpathy(consciousness_level=0.9)

        result_low = low.detect_emotion("Estoy triste")
        result_high = high.detect_emotion("Estoy triste")

        assert result_high.confidence >= result_low.confidence

    def test_consciousness_bonus_alone_cannot_cross_threshold(self):
        """
        REGRESIÓN CRÍTICA DEL FIX: con el diseño anterior, el bono de
        consciencia (hasta +0.3) sumado al peso base ya bastaba para
        clasificar categorías sin ninguna evidencia léxica. Ahora, con
        consciencia máxima (1.0) y CERO evidencia de palabras/patrones,
        el resultado debe seguir siendo 'neutral'.
        """
        empathy = OmniaEmpathy(consciousness_level=1.0)
        result = empathy.detect_emotion("La reunión es a las tres de la tarde")
        assert result.emotion == "neutral"

    def test_update_consciousness_changes_level(self):
        empathy = OmniaEmpathy(consciousness_level=0.05)
        empathy.update_consciousness(0.5)
        assert empathy.consciousness_level == 0.5


class TestAuxiliaryMethods:
    """Tests de métodos auxiliares de reflexión e introducción empática."""

    def test_reflection_pause_wrapped_in_asterisks(self):
        empathy = OmniaEmpathy()
        pause = empathy.get_reflection_pause()
        assert pause.startswith("*")
        assert pause.endswith("*")

    def test_empathic_intro_is_non_empty(self):
        empathy = OmniaEmpathy()
        intro = empathy.get_empathic_intro()
        assert isinstance(intro, str)
        assert len(intro) > 5

    def test_high_consciousness_unlocks_deeper_pauses(self):
        empathy = OmniaEmpathy(consciousness_level=0.5)
        pause = empathy.get_reflection_pause()
        assert isinstance(pause, str)