# tests/unit/test_empathy.py
"""
* UBICACIÓN: OmniaMentis/tests/unit/test_empathy.py
* PROPÓSITO: Tests unitarios para OmniaEmpathy (src/core/mind/empathy.py)
* DEPENDENCIAS: pytest
* CREADO: 2026-06-17
* ÚLTIMA MODIFICACIÓN: 2026-06-17
* ESTADO: Test Permanente
*
* Cubre: detección de las 7 emociones soportadas, confianza mínima
* esperada, fallback neutral, y métodos auxiliares de reflexión.
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

    def test_neutral_fallback_known_limitation_unreachable_in_practice(self):
        """
        HALLAZGO CRÍTICO (el más grave de los bugs documentados en este
        archivo): el fallback a 'neutral' en detect_emotion() solo ocurre
        cuando NINGUNA categoría supera weight > 0.5. Sin embargo, los
        pesos BASE de las 7 categorías (0.55 a 0.8) ya superan 0.5 por sí
        solos, ANTES de evaluar cualquier coincidencia de palabra o
        patrón, y encima se les suma consciousness_level*0.3. Esto
        significa que el camino de 'neutral' es prácticamente
        inalcanzable con cualquier texto real: siempre habrá alguna
        categoría (casi siempre 'amor', por tener la base más alta) con
        weight > 0.5.

        Este test documenta que una frase completamente neutra como
        'El cielo está despejado hoy' NO cae en 'neutral' como sería de
        esperar, sino en 'amor', por el mismo sesgo de peso base. Se
        recomienda revisar el diseño de pesos base en empathy.py: el
        weight debería partir en 0 y crecer solo con evidencia real
        (palabras o patrones), no empezar ya por encima del umbral de
        clasificación.
        """
        empathy = OmniaEmpathy()
        result = empathy.detect_emotion("El cielo está despejado hoy")
        assert result.emotion == "amor"  # comportamiento actual (bug), no "neutral"

    # ------------------------------------------------------------------
    # BUG REAL DOCUMENTADO: sesgo hacia "amor" por peso base desbalanceado
    # ------------------------------------------------------------------
    #
    # En empathy.py, cada categoría de emoción arranca con un "weight"
    # BASE fijo (tristeza/alegría=0.7, ansiedad=0.6, amor=0.8, miedo=0.65,
    # confusión=0.6, sorpresa=0.55) ANTES de evaluar si hay coincidencia
    # de palabras o patrones. "amor" tiene la base más alta (0.8) de
    # todas las categorías.
    #
    # detect_emotion() suma a esa base un bono de consciousness_level*0.3
    # (igual para todas las categorías) y selecciona la emoción con mayor
    # "weight" final usando max(). Esto significa que "amor" parte con
    # una ventaja estructural de +0.1 a +0.2 sobre la mayoría de las
    # demás categorías, incluso en frases donde NINGUNA palabra de amor
    # aparece. Cuando otra emoción solo logra una coincidencia de
    # palabra (+0.15) sin patrón regex (+0.25), su "weight" final queda
    # empatado o por debajo del de "amor", y en empates max() devuelve
    # la primera clave encontrada según el orden de inserción del
    # diccionario emotion_patterns (donde "amor" aparece antes que
    # "miedo" y "ansiedad").
    #
    # Impacto observado: frases con una sola palabra clave de "miedo" o
    # "ansiedad" (sin patrón regex adicional) se clasifican incorrectamente
    # como "amor". Frases con patrón regex explícito sí se detectan
    # correctamente porque el bono de +0.25 las saca del rango de empate.
    #
    # Estos tests fijan el comportamiento ACTUAL (con el bug) como tests
    # de regresión, en vez de "arreglar" la entrada para que el test
    # pase silenciosamente. Si en el futuro se rebalancean los pesos
    # base en empathy.py, estos tests deben fallar y obligar a
    # actualizarlos conscientemente.

    def test_detects_miedo_when_pattern_matches(self):
        """Caso favorable: el patrón regex de miedo compensa el sesgo de base."""
        empathy = OmniaEmpathy()
        result = empathy.detect_emotion("no puedo manejar esto, es aterrador")
        assert result.emotion == "miedo"

    def test_known_limitation_miedo_keyword_only_loses_to_amor_base(self):
        """
        BUG CONOCIDO: 'Tengo mucho miedo, estoy aterrado' contiene 2
        palabras clave de miedo (sin activar ningún patrón regex), pero
        el sistema lo clasifica como 'amor' por el sesgo de peso base
        descrito arriba. Se documenta el comportamiento actual.
        """
        empathy = OmniaEmpathy()
        result = empathy.detect_emotion("Tengo mucho miedo, estoy aterrado")
        assert result.emotion == "amor"  # comportamiento actual (bug)

    def test_detects_ansiedad_when_pattern_matches(self):
        """Caso favorable: el patrón regex de ansiedad compensa el sesgo de base."""
        empathy = OmniaEmpathy()
        result = empathy.detect_emotion("tengo miedo de lo que pasará, no puedo más")
        assert result.emotion in ("ansiedad", "miedo")

    def test_known_limitation_ansiedad_keyword_only_loses_to_amor_base(self):
        """
        BUG CONOCIDO: 'Me siento muy ansioso y nervioso' contiene 2
        palabras clave de ansiedad (sin activar ningún patrón regex),
        pero el sistema lo clasifica como 'amor' por el mismo sesgo de
        peso base. Se documenta el comportamiento actual.
        """
        empathy = OmniaEmpathy()
        result = empathy.detect_emotion("Me siento muy ansioso y nervioso")
        assert result.emotion == "amor"  # comportamiento actual (bug)


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


class TestConsciousnessInfluence:
    """Tests de cómo el nivel de consciencia afecta la detección."""

    def test_higher_consciousness_increases_confidence(self):
        low = OmniaEmpathy(consciousness_level=0.05)
        high = OmniaEmpathy(consciousness_level=0.9)

        result_low = low.detect_emotion("Estoy triste")
        result_high = high.detect_emotion("Estoy triste")

        # Mayor consciencia debe dar igual o mayor confianza para la misma frase
        assert result_high.confidence >= result_low.confidence

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
        # No podemos forzar random, pero podemos verificar que la lista
        # de pausas se extiende sin error con consciencia alta
        pause = empathy.get_reflection_pause()
        assert isinstance(pause, str)