# tests/unit/test_spacy_intent.py
"""
* UBICACIÓN: OmniaMentis/tests/unit/test_spacy_intent.py
* PROPÓSITO: Tests de SpaCyIntentClassifier (src/core/mind/spacy_intent.py)
* DEPENDENCIAS: pytest (SpaCy real es OPCIONAL: ver TestRealSpacy)
* CREADO: 2026-10-10
* ESTADO: Test Permanente
*
* DISEÑO: la lógica propia (vocabularios, puntuación, confianza, manejo
* de errores) se prueba con un "nlp" falso y determinista, para no
* depender de la versión del modelo es_core_news_sm ni de que SpaCy
* esté instalado. TestRealSpacy solo comprueba contratos que no
* dependen de cómo el modelo lematiza.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from core.mind.spacy_intent import (
    EMOTION_LEMMAS,
    INTENT_LEMMAS,
    IntentResult,
    SpaCyIntentClassifier,
)


class _Tok:
    def __init__(self, lemma, stop=False, alpha=True):
        self.lemma_ = lemma
        self.is_stop = stop
        self.is_alpha = alpha


class _FakeNlp:
    """Lematiza con un diccionario; palabras no listadas = su propio lema."""

    LEMMAS = {"deprimido": "deprimir", "aterrado": "aterrar", "llorando": "llorar"}
    STOP = {"me", "siento", "muy", "la", "el", "de", "que", "yo", "no", "a", "mi", "las", "y"}

    def __call__(self, text):
        out = []
        for w in text.split():
            clean = w.strip(".,!?¿¡")
            out.append(_Tok(self.LEMMAS.get(clean, clean), stop=clean in self.STOP,
                            alpha=clean.isalpha()))
        return out


def _classifier(nlp=None):
    c = SpaCyIntentClassifier.__new__(SpaCyIntentClassifier)
    c.model_name = "fake"
    c.nlp = nlp if nlp is not None else _FakeNlp()
    c.available = True
    return c


class TestVocabulary:
    # Lemas que en español cotidiano casi nunca expresan emoción y que
    # antes producían falsos positivos.
    AMBIGUOUS = ("querer", "solo", "perder", "perdido")

    def test_ambiguous_lemmas_not_in_emotion_vocabulary(self):
        for emotion, lemmas in EMOTION_LEMMAS.items():
            for bad in self.AMBIGUOUS:
                assert bad not in lemmas, f"{bad!r} sigue en {emotion}"

    def test_no_multiword_entries(self):
        """Un lema suelto nunca puede coincidir con una frase de 2+ palabras."""
        for vocab in (EMOTION_LEMMAS, INTENT_LEMMAS):
            for category, lemmas in vocab.items():
                for lemma in lemmas:
                    assert " " not in lemma, f"{lemma!r} en {category}"

    def test_no_duplicate_lemmas_within_a_category(self):
        for vocab in (EMOTION_LEMMAS, INTENT_LEMMAS):
            for category, lemmas in vocab.items():
                assert len(lemmas) == len(set(lemmas)), category


class TestClassify:
    def test_unavailable_returns_flagged_neutral(self):
        c = SpaCyIntentClassifier.__new__(SpaCyIntentClassifier)
        c.nlp = None
        c.available = False
        r = c.classify("estoy triste")
        assert r.available is False
        assert r.emotion == "neutral"

    def test_detects_emotion_through_lemma(self):
        r = _classifier().classify("Me siento muy deprimido")
        assert r.emotion == "tristeza"
        assert "deprimir" in r.lemmas
        assert r.available is True

    def test_confidence_is_proportion_times_three_capped(self):
        r = _classifier().classify("deprimido")  # 1 lema, 1 match -> 3.0 -> tope 1.0
        assert r.confidence == 1.0
        r2 = _classifier().classify("deprimido mesa silla perro casa gato")  # 1/6*3
        assert r2.confidence == 0.5

    def test_everyday_request_with_quiero_is_neutral(self):
        r = _classifier().classify("quiero saber la hora")
        assert r.emotion == "neutral"
        assert r.confidence == 0.0

    def test_solo_does_not_mean_sadness(self):
        r = _classifier().classify("solo necesito ayuda con una tarea")
        assert r.emotion == "neutral"

    def test_lost_keys_is_not_sadness_or_confusion(self):
        r = _classifier().classify("perdí las llaves")
        assert r.emotion == "neutral"

    def test_stop_words_and_non_alpha_are_filtered(self):
        r = _classifier().classify("me siento 123 deprimido")
        assert "123" not in r.lemmas
        assert "me" not in r.lemmas

    @pytest.mark.parametrize("text", ["", "   ", None, 42])
    def test_empty_or_invalid_input_does_not_crash(self, text):
        r = _classifier().classify(text)
        assert r.emotion == "neutral"
        assert r.confidence == 0.0
        assert r.available is True

    def test_internal_spacy_error_is_contained(self):
        class Boom:
            def __call__(self, text):
                raise RuntimeError("fallo interno")

        r = _classifier(Boom()).classify("estoy triste")
        assert r.available is False
        assert r.emotion == "neutral"

    def test_tie_between_categories_is_deterministic(self):
        # "angustia" está en varias categorías: el resultado debe ser siempre el mismo.
        results = {_classifier().classify("angustia").emotion for _ in range(5)}
        assert len(results) == 1

    def test_intent_detected_independently_of_emotion(self):
        r = _classifier().classify("quiero organizar mi plan")
        assert r.intent == "orden"


class TestScoreCategory:
    def test_no_match_returns_neutral_zero(self):
        assert _classifier()._score_category(["mesa"], EMOTION_LEMMAS) == ("neutral", 0)

    def test_best_category_wins(self):
        cat, score = _classifier()._score_category(["triste", "llorar", "feliz"], EMOTION_LEMMAS)
        assert (cat, score) == ("tristeza", 2)


@pytest.fixture(scope="module")
def real():
    """Clasificador con el modelo real; se omite si no está instalado."""
    c = SpaCyIntentClassifier()
    if not c.available:
        pytest.skip("SpaCy o es_core_news_sm no instalados")
    return c


class TestRealSpacy:
    """Contratos mínimos con el modelo real; se omiten si no está instalado."""

    def test_returns_intent_result_with_valid_ranges(self, real):
        r = real.classify("Hoy me siento muy triste y no sé qué hacer")
        assert isinstance(r, IntentResult)
        assert r.available is True
        assert 0.0 <= r.confidence <= 1.0
        assert isinstance(r.lemmas, list)

    def test_neutral_sentence_has_no_emotion(self, real):
        r = real.classify("La reunión es a las tres de la tarde")
        assert r.emotion == "neutral"

    def test_empty_text_is_safe(self, real):
        assert real.classify("").emotion == "neutral"