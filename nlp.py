"""
Sentiment classification for Hebrew and English news articles.

Hebrew articles route to a Hebrew-specialized model (DictaBERT).
English articles route to a RoBERTa variant trained on social and news text.

This version returns the full probability distribution across all three
classes (negative, neutral, positive) for every classification call, and
supports separate classification of headline vs combined headline+snippet
for divergence analysis (a divergence between headline tone and body tone
is a signal of clickbait or misleading framing).

The classifier loads models lazily on first use to keep startup fast for
non-NLP commands (e.g., running the dashboard against pre-classified data).
"""

import logging
from dataclasses import dataclass
from typing import Optional, List, Dict

from config import HEBREW_SENTIMENT_MODEL, ENGLISH_SENTIMENT_MODEL

logger = logging.getLogger(__name__)


@dataclass
class SentimentResult:
    """Output of sentiment classification with full probability distribution."""

    label: str          # winning class: positive / neutral / negative
    score: float        # probability of the winning class
    neg_score: float    # probability of negative class
    neu_score: float    # probability of neutral class
    pos_score: float    # probability of positive class
    model: str

    def to_dict(self, prefix: str = "sentiment") -> dict:
        """
        Serialize to dict with a configurable column prefix.
        prefix='sentiment'           -> sentiment_label, sentiment_score, ...
        prefix='headline_sentiment'  -> headline_sentiment_label, headline_sentiment_score, ...
        """
        return {
            f"{prefix}_label": self.label,
            f"{prefix}_score": round(self.score, 4),
            f"{prefix}_neg_score": round(self.neg_score, 4),
            f"{prefix}_neu_score": round(self.neu_score, 4),
            f"{prefix}_pos_score": round(self.pos_score, 4),
            f"{prefix}_model": self.model,
        }


class SentimentClassifier:
    """Lazy-loading classifier with separate Hebrew and English pipelines.
    Returns full probability distribution for each call.
    """

    LABEL_MAP = {
        "POSITIVE": "positive",
        "NEGATIVE": "negative",
        "NEUTRAL": "neutral",
        "positive": "positive",
        "negative": "negative",
        "neutral": "neutral",
        # DictaBERT-sentiment may emit Hebrew labels
        "חיובי": "positive",
        "שלילי": "negative",
        "ניטרלי": "neutral",
        "Positive": "positive",
        "Negative": "negative",
        "Neutral": "neutral",
        # RoBERTa Cardiff variant
        "LABEL_0": "negative",
        "LABEL_1": "neutral",
        "LABEL_2": "positive",
    }

    def __init__(self):
        self._hebrew_pipeline = None
        self._english_pipeline = None

    def _load_hebrew(self):
        if self._hebrew_pipeline is None:
            from transformers import pipeline
            logger.info(f"Loading Hebrew sentiment model: {HEBREW_SENTIMENT_MODEL}")
            self._hebrew_pipeline = pipeline(
                "sentiment-analysis",
                model=HEBREW_SENTIMENT_MODEL,
                truncation=True,
                max_length=512,
                top_k=None,  # return all class probabilities, not just the winner
            )
        return self._hebrew_pipeline

    def _load_english(self):
        if self._english_pipeline is None:
            from transformers import pipeline
            logger.info(f"Loading English sentiment model: {ENGLISH_SENTIMENT_MODEL}")
            self._english_pipeline = pipeline(
                "sentiment-analysis",
                model=ENGLISH_SENTIMENT_MODEL,
                truncation=True,
                max_length=512,
                top_k=None,  # return all class probabilities, not just the winner
            )
        return self._english_pipeline

    def _scores_by_class(self, raw_results: List[Dict]) -> Dict[str, float]:
        """Convert raw HF output (list of {label, score}) into a dict
        keyed by normalized class name."""
        out = {"negative": 0.0, "neutral": 0.0, "positive": 0.0}
        for item in raw_results:
            normalized = self.LABEL_MAP.get(item["label"], item["label"].lower())
            if normalized in out:
                out[normalized] = float(item["score"])
        return out

    def classify(self, text: str, language: str) -> Optional[SentimentResult]:
        """
        Classify a single piece of text.

        Args:
            text: text to classify (e.g., headline alone, or headline + snippet)
            language: 'he' for Hebrew, 'en' for English

        Returns:
            SentimentResult with all three class probabilities, or None on error.
        """
        if not text or not text.strip():
            return None

        try:
            if language == "he":
                pipe = self._load_hebrew()
                model_name = HEBREW_SENTIMENT_MODEL
            elif language == "en":
                pipe = self._load_english()
                model_name = ENGLISH_SENTIMENT_MODEL
            else:
                logger.warning(f"Unknown language: {language}")
                return None

            # With top_k=None, the pipeline returns [[{label, score}, ...]]
            raw_results = pipe(text[:512])[0]
            scores = self._scores_by_class(raw_results)

            # Identify the winning class
            winning_label = max(scores, key=scores.get)
            winning_score = scores[winning_label]

            return SentimentResult(
                label=winning_label,
                score=winning_score,
                neg_score=scores["negative"],
                neu_score=scores["neutral"],
                pos_score=scores["positive"],
                model=model_name,
            )
        except Exception as e:
            logger.error(f"Classification failed: {e}")
            return None

    def classify_article(
        self,
        headline: str,
        snippet: str,
        language: str,
    ) -> dict:
        """
        Classify both the combined text (headline + snippet) and the headline alone.
        Returns a single flat dict suitable for merging into an article record.

        Combined classification populates fields with prefix 'sentiment_'.
        Headline-only classification populates fields with prefix 'headline_sentiment_'.

        If either classification fails, the corresponding fields are simply absent
        from the returned dict (caller can still merge it without overwriting).
        """
        out = {}

        combined = f"{headline}. {snippet}".strip()
        combined_result = self.classify(combined, language)
        if combined_result:
            out.update(combined_result.to_dict(prefix="sentiment"))

        if headline and headline.strip():
            headline_result = self.classify(headline.strip(), language)
            if headline_result:
                out.update(headline_result.to_dict(prefix="headline_sentiment"))

        return out


# Module-level singleton (so models load once across the pipeline)
_classifier: Optional[SentimentClassifier] = None


def get_classifier() -> SentimentClassifier:
    """Get or create the singleton classifier."""
    global _classifier
    if _classifier is None:
        _classifier = SentimentClassifier()
    return _classifier


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")

    classifier = get_classifier()

    samples = [
        ("הכנסת אישרה היום בקריאה ראשונה את חוק התקציב",
         "תיקון חוק התקציב עבר ברוב של 62 חברי כנסת תוך התנגדות מהאופוזיציה",
         "he"),
        ("Israeli soldiers wounded near Gaza border",
         "Two soldiers were lightly injured after gunfire from the Gaza strip toward a patrol",
         "en"),
        ("שר הביטחון: השגנו את כל יעדי המבצע",
         "השר הצהיר במסיבת עיתונאים כי המבצע הצליח מעבר לציפיות",
         "he"),
    ]

    for headline, snippet, lang in samples:
        print(f"\n[{lang}] {headline}")
        result = classifier.classify_article(headline, snippet, lang)
        for k, v in result.items():
            print(f"  {k}: {v}")
