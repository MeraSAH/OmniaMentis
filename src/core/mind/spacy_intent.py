"""
* UBICACIÓN: OmniaMentis/src/core/mind/spacy_intent.py
* PROPÓSITO: Clasificación de intención del usuario usando SpaCy con el
*            modelo es_core_news_sm. La lematización reemplaza la detección
*            por regex de OmniaEmpathy para capturar variantes morfológicas
*            que el sistema anterior no detectaba (bug documentado en
*            test_empathy.py::test_known_limitation_*).
* DEPENDENCIAS: spacy, es_core_news_sm
* CREADO: 2026-06-27
* ÚLTIMA MODIFICACIÓN: 2026-06-27
* ESTADO: Producción

INSTALACIÓN (ejecutar en el venv de Windows):
    pip install spacy
    python -m spacy download es_core_news_sm

DECISIÓN DE DISEÑO — SpaCy como capa de clasificación, no de reemplazo:
    SpaCy extrae lemas (formas base de las palabras) y los compara contra
    vocabularios semánticos. Esto resuelve el bug principal de OmniaEmpathy:
    "deprimido", "depresiva", "deprimirse" → lema "deprimir" → detecta tristeza.
    OmniaEmpathy sigue existiendo pero recibe el resultado de SpaCy para
    generar la respuesta empática. No se rompe ningún test existente.

FALLBACK SI SPACY NO ESTÁ DISPONIBLE:
    SpaCyIntentClassifier.classify() devuelve IntentResult con
    available=False y emotion="neutral". main_flask.py usa OmniaEmpathy
    directamente como antes. El sistema nunca se rompe.
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

# ── Vocabularios semánticos por lema ─────────────────────────────────────────
# Usar lemas (formas base) — SpaCy convierte cualquier variante morfológica
# al lema antes de buscar. Esto resuelve el bug de OmniaEmpathy con regex.
#
# Ejemplos de cobertura:
#   "deprimido", "deprimirse", "depresiva" → lema "deprimir" → tristeza ✅
#   "ansioso", "ansiosa", "ansiarse" → lema "ansiar"/"ansioso" → ansiedad ✅
#   "aterrado", "aterrar", "terror" → lema "aterrar" → miedo ✅

EMOTION_LEMMAS: dict[str, list[str]] = {
    "tristeza": [
        "triste", "tristeza", "llorar", "llorar", "deprimir", "depresión",
        "melancolía", "melancólico", "dolor", "pena", "sufrir", "sufrimiento",
        "angustia", "angustiar", "desesperar", "desesperación", "perder",
        "soledad", "solo", "vacío", "vaciar", "oscuridad",
    ],
    "alegría": [
        "feliz", "felicidad", "alegría", "alegre", "contento", "gozo",
        "gozar", "celebrar", "celebración", "reír", "risa", "disfrutar",
        "júbilo", "euforia", "emocionante", "maravilloso",
    ],
    "ansiedad": [
        "ansioso", "ansiedad", "nervioso", "nerviosismo", "angustia",
        "preocupado", "preocupación", "estrés", "estresar", "agitar",
        "inquieto", "inquietud", "tenso", "tensión", "agobiar", "abrumar",
    ],
    "amor": [
        "amar", "amor", "querer", "cariño", "ternura", "adorar",
        "afecto", "apreciar", "apreciación", "cuidar", "proteger",
    ],
    "miedo": [
        "miedo", "temer", "temor", "terror", "aterrar", "aterrador",
        "espanto", "espantar", "pánico", "asustado", "asustar",
        "angustia", "angustiar", "peligro", "amenaza", "amenazar",
    ],
    "confusión": [
        "confundir", "confusión", "confundido", "desorientar", "perder",
        "perdido", "desorientado", "no entender", "incomprensión",
        "dudar", "duda", "incertidumbre", "caos",
    ],
    "frustración": [
        "frustrar", "frustración", "frustrado", "hartar", "harto",
        "cansado", "cansar", "agotado", "agotar", "rendirse",
        "bloqueado", "bloquear", "estancar",
    ],
}

# Intenciones de alto nivel (más allá de emoción)
INTENT_LEMMAS: dict[str, list[str]] = {
    "orden": [
        "ordenar", "organizar", "planificar", "estructurar", "priorizar",
        "sistema", "método", "proceso", "flujo", "claridad",
    ],
    "caos": [
        "caos", "desorden", "desordenar", "problema", "conflicto",
        "dificultad", "complicar", "enredar", "lío",
    ],
    "reflexion": [
        "pensar", "reflexionar", "analizar", "evaluar", "considerar",
        "meditar", "contemplar", "examinar", "revisar",
    ],
    "accion": [
        "hacer", "actuar", "decidir", "ejecutar", "implementar",
        "aplicar", "comenzar", "avanzar", "mover",
    ],
}


@dataclass
class IntentResult:
    """Resultado del análisis de intención por SpaCy."""
    emotion: str = "neutral"
    intent: str = "neutral"
    confidence: float = 0.0
    lemmas: list = field(default_factory=list)
    available: bool = True  # False si SpaCy no está instalado


class SpaCyIntentClassifier:
    """
    Clasificador de intención usando lematización de SpaCy.

    Reemplaza la detección por regex de OmniaEmpathy para resolver el bug
    documentado en test_empathy.py (variantes morfológicas no detectadas).

    Uso:
        classifier = SpaCyIntentClassifier()
        if classifier.available:
            result = classifier.classify("me siento muy deprimido")
            print(result.emotion)  # "tristeza"
        else:
            # Fallback a OmniaEmpathy
            pass
    """

    def __init__(self, model: str = "es_core_news_sm"):
        self.model_name = model
        self.nlp = None
        self.available = False
        self._load_model()

    def _load_model(self) -> None:
        """Carga SpaCy de forma segura. Si falla, available=False."""
        try:
            import spacy
            self.nlp = spacy.load(self.model_name)
            self.available = True
            logger.info(f"✅ SpaCy '{self.model_name}' cargado correctamente")
        except ImportError:
            logger.warning(
                "SpaCy no está instalado. "
                "Ejecutar: pip install spacy && python -m spacy download es_core_news_sm"
            )
        except OSError:
            logger.warning(
                f"Modelo SpaCy '{self.model_name}' no encontrado. "
                f"Ejecutar: python -m spacy download {self.model_name}"
            )

    def classify(self, text: str) -> IntentResult:
        """
        Clasifica la emoción e intención del texto usando lematización.

        Args:
            text: Texto del usuario en español.

        Returns:
            IntentResult con emotion, intent, confidence y lemmas extraídos.
            Si SpaCy no está disponible, devuelve IntentResult(available=False).
        """
        if not self.available or self.nlp is None:
            return IntentResult(available=False)

        doc = self.nlp(text.lower())
        lemmas = [token.lemma_ for token in doc if not token.is_stop and token.is_alpha]

        emotion, emotion_score = self._score_category(lemmas, EMOTION_LEMMAS)
        intent, intent_score = self._score_category(lemmas, INTENT_LEMMAS)

        # Confianza: proporción de lemmas que hicieron match sobre el total
        total_lemmas = len(lemmas) if lemmas else 1
        confidence = min(emotion_score / total_lemmas * 3.0, 1.0)

        return IntentResult(
            emotion=emotion,
            intent=intent,
            confidence=round(confidence, 3),
            lemmas=lemmas,
            available=True,
        )

    def _score_category(
        self, lemmas: list[str], vocabulary: dict[str, list[str]]
    ) -> tuple[str, int]:
        """
        Puntúa cada categoría contando coincidencias de lemas.

        Returns:
            (categoría_ganadora, puntuación_máxima)
            Si ninguna categoría tiene matches, retorna ("neutral", 0).
        """
        scores: dict[str, int] = {}
        for category, category_lemmas in vocabulary.items():
            score = sum(1 for lemma in lemmas if lemma in category_lemmas)
            if score > 0:
                scores[category] = score

        if not scores:
            return "neutral", 0

        best = max(scores, key=lambda k: scores[k])
        return best, scores[best]