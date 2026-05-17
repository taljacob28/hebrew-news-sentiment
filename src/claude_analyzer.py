"""
Advanced article analysis via Claude API.

Three layers of analysis per article:
1. Fine-grained emotions (joy, anger, fear, sadness, surprise, disgust, pride, anticipation)
2. Named Entity Recognition (people, parties, organizations, locations)
3. Topic classification (auto-detected themes beyond politics/security)

All three are extracted in a single API call per article for efficiency.
Results are returned as structured JSON.
"""

import json
import logging
import os
import time
from dataclasses import dataclass, asdict
from typing import Optional, List

from dotenv import load_dotenv
from anthropic import Anthropic

load_dotenv()

logger = logging.getLogger(__name__)


@dataclass
class ClaudeAnalysis:
    """Output of Claude analysis on a single article."""
    emotion_label: str
    emotion_intensity: float
    entities: List[dict]
    topic_label: str
    topic_master: str
    topic_confidence: float

    def to_dict(self):
        return {
            "emotion_label": self.emotion_label,
            "emotion_intensity": self.emotion_intensity,
            "entities_json": json.dumps(self.entities, ensure_ascii=False),
            "topic_label": self.topic_label,
            "topic_master": self.topic_master,
            "topic_confidence": self.topic_confidence,
        }


class ClaudeAnalyzer:
    """Analyzes articles using Claude API for advanced NLP layers."""

    MODEL = "claude-haiku-4-5"
    MAX_TOKENS = 600

    SYSTEM_PROMPT = """You are an expert news analyst specializing in Israeli politics and security coverage.

For each article headline and snippet provided, return ONLY a valid JSON object with this exact structure:

{
  "emotion_label": "<one of: joy, anger, fear, sadness, surprise, disgust, pride, anticipation, neutral>",
  "emotion_intensity": <float 0.0 to 1.0>,
  "entities": [
    {"name": "<entity name in English>", "type": "<one of: person, party, organization, location, event>"}
  ],
  "topic_label": "<short topic descriptor in English, 2-5 words>",
  "topic_master": "<MUST be one of: Iran-Israel Relations, Lebanon & Hezbollah, Gaza & Hamas, Coalition & Government, Knesset & Legislation, Judicial & Legal, Domestic Politics, Security Operations, International Diplomacy, Social & Civil, Economic Affairs, Other>",
  "topic_confidence": <float 0.0 to 1.0>
}

CRITICAL RULES FOR ENTITIES:
- ALL entity names MUST be in English, even if the article is in Hebrew
- Translate Hebrew names to their standard English form
- Examples of required translations:
  * צה"ל -> IDF
  * חיזבאללה -> Hezbollah
  * חמאס -> Hamas
  * לבנון -> Lebanon
  * עזה -> Gaza
  * נתניהו -> Benjamin Netanyahu
  * בנימין נתניהו -> Benjamin Netanyahu
  * לפיד -> Yair Lapid
  * יאיר לפיד -> Yair Lapid
  * גנץ -> Benny Gantz
  * בני גנץ -> Benny Gantz
  * נפתלי בנט -> Naftali Bennett
  * בן גביר -> Itamar Ben-Gvir
  * סמוטריץ' -> Bezalel Smotrich
  * ליכוד -> Likud
  * יש עתיד -> Yesh Atid
  * ש"ס -> Shas
  * המחנה הממלכתי -> National Unity Party
  * הכנסת -> Knesset
  * שב"כ -> Shin Bet
  * המוסד -> Mossad
  * דרום לבנון -> Southern Lebanon
- For people: use full English name (e.g., "Benjamin Netanyahu" not "Netanyahu")
- For organizations: use the most common English name
- NEVER return entity names in Hebrew, Arabic, or other non-Latin scripts

Other rules:
- emotion_intensity: how strongly the emotion is expressed (0=mild, 1=intense)
- entities: extract up to 5 most important named entities
- topic_label: short, specific topic (e.g., "judicial reform protest", "Gaza ceasefire negotiations", "coalition crisis")
- topic_master: MUST be exactly one of the 12 categories listed above. Pick the best match.
- Return ONLY the JSON, no preamble or explanation
- Respond with valid JSON even if the article is in Hebrew"""

    def __init__(self):
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY not found in environment")
        self.client = Anthropic(api_key=api_key)

    def analyze(self, headline: str, snippet: str) -> Optional[ClaudeAnalysis]:
        """Run full analysis on a single article."""
        text = f"Headline: {headline}\n\nSnippet: {snippet[:500]}"

        try:
            response = self.client.messages.create(
                model=self.MODEL,
                max_tokens=self.MAX_TOKENS,
                system=self.SYSTEM_PROMPT,
                messages=[
                    {"role": "user", "content": text},
                    {"role": "assistant", "content": "{"},
                ],
            )
            raw = "{" + response.content[0].text.strip()
            # Extract JSON if there's text around it
            if "{" in raw and "}" in raw:
                start = raw.find("{")
                end = raw.rfind("}") + 1
                raw = raw[start:end]
            data = json.loads(raw)

            return ClaudeAnalysis(
                emotion_label=data.get("emotion_label", "neutral"),
                emotion_intensity=float(data.get("emotion_intensity", 0.5)),
                entities=data.get("entities", []),
                topic_label=data.get("topic_label", "general"),
                topic_master=data.get("topic_master", "Other"),
                topic_confidence=float(data.get("topic_confidence", 0.5)),
            )
        
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse Claude response: {e}")
            return None
        except Exception as e:
            logger.error(f"Claude API error: {e}")
            return None

    def analyze_batch(self, articles: list, delay: float = 0.3) -> dict:
        """Analyze multiple articles. Returns dict mapping article_hash to analysis."""
        results = {}
        for i, article in enumerate(articles):
            if i > 0 and i % 10 == 0:
                logger.info(f"  Analyzed {i}/{len(articles)} articles")
            analysis = self.analyze(article.get("headline", ""), article.get("snippet", ""))
            if analysis:
                results[article["hash"]] = analysis.to_dict()
            time.sleep(delay)
        return results


def get_analyzer() -> ClaudeAnalyzer:
    return ClaudeAnalyzer()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
    
    analyzer = get_analyzer()
    
    test_headline = "ראש הממשלה הודיע על הקמת ועדת חקירה ממלכתית"
    test_snippet = "בנימין נתניהו הודיע היום בכנסת על הקמת ועדה לבחינת אירועי השבועות האחרונים. בקואליציה מברכים, באופוזיציה תוקפים."
    
    print(f"Analyzing: {test_headline}")
    result = analyzer.analyze(test_headline, test_snippet)
    
    if result:
        print(f"\nEmotion: {result.emotion_label} (intensity: {result.emotion_intensity})")
        print(f"Topic: {result.topic_label} (confidence: {result.topic_confidence})")
        print(f"\nEntities:")
        for entity in result.entities:
            print(f"  - {entity['name']} ({entity['type']})")
    else:
        print("Analysis failed")