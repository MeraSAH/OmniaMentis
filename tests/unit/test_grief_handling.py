# tests/unit/test_grief_handling.py
"""
* UBICACIÓN: OmniaMentis/tests/unit/test_grief_handling.py
* PROPÓSITO: Regresión del hallazgo 2026-10-09 sobre mensajes de pérdida
  (empathy.py + prompt de ollama_client.py).
* ESTADO: Test Permanente

Hallazgo real: "Mi mejor amigo a fallecido" se clasificaba "neutral" y
"perdí a mi mejor amigo" hacía que llama3.2 supusiera una pérdida de
contacto. Ahora el fallecimiento se reconoce como duelo, y la pérdida
ambigua se acompaña sin suponer la causa.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from core.mind.empathy import OmniaEmpathy
from core.llm.ollama_client import OllamaClient


def grief(text, level=0.16):
    return OmniaEmpathy(consciousness_level=level).detect_grief_subtype(text)


class TestDeathVocabulary:

    def test_fallecido_with_typo_is_duelo(self):
        r = grief("Mi mejor amigo a fallecido")
        assert r is not None and r.subtype == "duelo"

    def test_ha_fallecido_is_duelo(self):
        assert grief("mi abuelo ha fallecido").subtype == "duelo"

    def test_fallecida_is_duelo(self):
        assert grief("mi madre fallecida hace poco").subtype == "duelo"

    def test_murio_without_accent_is_duelo(self):
        assert grief("murio mi abuela").subtype == "duelo"

    def test_murio_with_accent_is_duelo(self):
        assert grief("mi perro murió ayer").subtype == "duelo"

    def test_ha_muerto_is_duelo(self):
        assert grief("mi tío ha muerto").subtype == "duelo"

    def test_works_even_at_baseline_consciousness(self):
        assert grief("mi amigo ha fallecido", level=0.05).subtype == "duelo"

    def test_response_is_the_duelo_template(self):
        r = grief("mi abuelo ha fallecido")
        assert "duelo" in r.response.lower() or "ausencia" in r.response.lower()


class TestAmbiguousLoss:

    def test_perdi_a_mi_mejor_amigo_is_generic_sadness_not_duelo(self):
        """Ambiguo (muerte vs pérdida de contacto): no se inventa matiz."""
        r = grief("perdí a mi mejor amigo")
        assert r is not None
        assert r.base_emotion == "tristeza"
        assert r.subtype is None


class TestNoFalsePositives:

    def test_happy_text_has_no_grief(self):
        assert grief("estoy feliz y contento") is None

    def test_greeting_has_no_grief(self):
        assert grief("hola, ¿cómo estás?") is None

    def test_died_laughing_is_not_grief(self):
        assert grief("se murió de risa con el chiste") is None

    def test_movie_death_is_not_grief(self):
        assert grief("el rey murió en la película") is None

    def test_third_person_news_is_not_grief(self):
        assert grief("hoy fallecieron dos pacientes en el hospital") is None

    def test_plural_possessive_death_is_grief(self):
        assert grief("murieron mis padres").subtype == "duelo"


class TestPromptDoesNotAssumeCause:

    def _prompt(self, emotion):
        return OllamaClient()._build_system_prompt(0.16, 2, emotion, 0.5, None, None)

    def test_sadness_prompt_tells_model_not_to_assume_cause(self):
        p = self._prompt("tristeza")
        assert "no supongas la causa" in p
        assert "[" not in p and "]" not in p  # sin corchetes (ver changelog de ollama_client)

    def test_other_emotions_do_not_get_the_loss_rule(self):
        assert "no supongas la causa" not in self._prompt("alegría")
        assert "no supongas la causa" not in self._prompt(None)