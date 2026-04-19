from __future__ import annotations

import csv
import json
import random
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import nltk
from langdetect import detect
from nltk.sentiment import SentimentIntensityAnalyzer
from nltk.tokenize import sent_tokenize

import argostranslate.package
import argostranslate.translate


ATTRIBUTE_KEYWORDS: Dict[str, Sequence[str]] = {
    "performance": [
        "fast", "faster", "slow", "lag", "laggy", "smooth", "fluid", "snappy",
        "responsive", "speed", "performance", "power", "powerful", "processor",
        "chip", "cpu", "gpu", "a19", "benchmark", "multitasking",
        "overheating", "heat", "thermal", "throttle", "stutter", "freeze",
        "crash", "loading", "load time"
    ],
    "battery": [
        "battery", "battery life", "battery drain", "battery health",
        "charge", "charging", "charger", "charging speed", "fast charge",
        "wireless charging", "magsafe", "power", "power usage",
        "lasts", "lasting", "drain", "drains", "dies", "all day",
        "screen on time", "sot", "endurance"
    ],
    "camera": [
        "camera", "photo", "photos", "picture", "pictures",
        "video", "recording", "4k", "hdr", "dolby vision",
        "portrait", "selfie", "front camera", "rear camera",
        "zoom", "optical zoom", "digital zoom",
        "low light", "night mode", "stabilization", "ois", "eis",
        "focus", "autofocus", "sharpness", "detail", "colors",
        "dynamic range", "lens", "sensor"
    ],
    "display": [
        "display", "screen", "panel", "oled", "amoled", "lcd",
        "retina", "resolution", "ppi", "brightness", "bright",
        "dim", "contrast", "colors", "color accuracy",
        "refresh rate", "120hz", "60hz", "hz",
        "touch", "touchscreen", "responsiveness",
        "outdoor visibility", "glare", "reflection"
    ],
    "design": [
        "design", "build", "build quality", "material", "finish",
        "premium", "cheap", "solid", "sturdy", "durable",
        "glass", "aluminum", "frame", "back",
        "look", "appearance", "style", "aesthetic",
        "color", "colors",
        "weight", "light", "heavy",
        "size", "compact", "big", "small",
        "ergonomics", "feel in hand", "grip"
    ],
    "software": [
        "ios", "software", "update", "updates",
        "os", "operating system",
        "ui", "interface", "user interface",
        "ux", "user experience",
        "features", "functions", "functionality",
        "bugs", "bug", "glitch", "issues",
        "crash", "freeze", "lag",
        "apple intelligence", "ai", "assistant",
        "apps", "app compatibility"
    ],
    "storage": [
        "storage", "memory", "capacity",
        "gb", "256gb", "512gb", "1tb",
        "space", "internal storage",
        "ram", "8gb ram", "multitasking memory",
        "expandable", "sd card"
    ],
    "connectivity": [
        "5g", "4g", "lte", "signal", "reception",
        "wifi", "wi-fi", "bluetooth",
        "connection", "connectivity",
        "calls", "call quality", "signal strength",
        "internet", "data", "network",
        "nfc", "gps", "location",
        "usb", "usb-c", "port"
    ],
    "audio": [
        "sound", "audio", "speaker", "speakers",
        "loudspeaker", "volume", "loud", "quiet",
        "stereo", "bass", "clarity",
        "microphone", "mic", "recording",
        "call quality", "voice",
        "headphone", "earbuds"
    ],
    "security": [
        "face id", "fingerprint", "touch id",
        "biometric", "unlock", "authentication",
        "security", "privacy", "secure"
    ],
    "hardware": [
        "sensor", "accelerometer", "gyro",
        "proximity sensor", "compass",
        "barometer", "face recognition",
        "haptic", "vibration", "motor"
    ],
    "value": [
        "price", "cost", "expensive", "cheap",
        "value", "value for money",
        "worth", "worth it", "overpriced",
        "deal", "discount", "offer",
        "quality price", "price quality"
    ]
}

SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+|\n+")
NLTK_RESOURCES = ("punkt", "punkt_tab", "vader_lexicon")


@dataclass
class TranslationResult:
    text_en: str
    language: str
    translated: bool


@dataclass
class ReviewRecord:
    source_file: str
    product_name: str
    webshop_name: str
    webshop_url: str
    rating: Optional[float]
    review_date: Optional[str]
    author: str
    title_original: str
    body_original: str
    title_english: str
    body_english: str
    language_code: str
    was_translated: bool
    insights: List[Dict[str, Any]]


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def parse_rating(rating_text: str, webshop_name: str = "") -> Optional[float]:
    if not rating_text:
        return None
    match = re.search(r"(\d+(?:\.\d+)?)", rating_text)
    if not match:
        return None
    rating = float(match.group(1))
    if webshop_name.lower() == "mediamarkt":
        rating *= 2
    return rating


def parse_date(date_text: str) -> Optional[str]:
    from datetime import datetime

    if not date_text:
        return None
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(date_text.strip(), fmt).date().isoformat()
        except ValueError:
            continue
    return None


def infer_webshop_name(url: str) -> str:
    from urllib.parse import urlparse

    domain = urlparse(url).netloc.lower().replace("www.", "")
    if not domain:
        return "unknown"
    primary = domain.split(".")[0]
    return primary.replace("-", " ").title()


def detect_language_safe(text: str) -> str:
    text = normalize_text(text)
    if not text:
        return "unknown"
    try:
        return detect(text)
    except Exception:
        return "unknown"


def has_review_description(title: str, body: str) -> bool:
    return bool(normalize_text(body))


def ensure_nltk_resources() -> None:
    for resource in NLTK_RESOURCES:
        try:
            if resource == "vader_lexicon":
                nltk.data.find("sentiment/vader_lexicon.zip")
            else:
                nltk.data.find(f"tokenizers/{resource}")
        except LookupError:
            nltk.download(resource, quiet=True)


class NLTKTextAnalyzer:
    def __init__(self) -> None:
        ensure_nltk_resources()
        self._sia = SentimentIntensityAnalyzer()

    def split_sentences(self, text: str) -> List[str]:
        normalized = normalize_text(text)
        if not normalized:
            return []
        try:
            return [normalize_text(s) for s in sent_tokenize(normalized) if normalize_text(s)]
        except Exception:
            return [normalize_text(s) for s in SENTENCE_SPLIT_RE.split(normalized) if normalize_text(s)]

    def vader_scores(self, text: str) -> Dict[str, float]:
        return self._sia.polarity_scores(text)


class Translator:
    """Local translator using Argos Translate for offline translation."""

    def __init__(self) -> None:
        self._cache: Dict[str, TranslationResult] = {}
        self._translation_cache: Dict[str, Any] = {}
        self._package_index_ready = False

    def _normalize_language_code(self, language_code: str) -> Optional[str]:
        if not language_code:
            return None
        return language_code.split("-")[0].lower()

    def _ensure_package_index(self) -> None:
        if self._package_index_ready:
            return
        try:
            argostranslate.package.update_package_index()
        except Exception:
            pass
        self._package_index_ready = True

    def _get_installed_language(self, language_code: str) -> Optional[Any]:
        normalized = self._normalize_language_code(language_code)
        if not normalized:
            return None
        for language in argostranslate.translate.get_installed_languages():
            if getattr(language, "code", "").lower() == normalized:
                return language
        return None

    def _install_language_pair(self, from_code: str, to_code: str) -> bool:
        self._ensure_package_index()
        try:
            available_packages = argostranslate.package.get_available_packages()
            package_to_install = next(
                (
                    package
                    for package in available_packages
                    if getattr(package, "from_code", "").lower() == from_code
                    and getattr(package, "to_code", "").lower() == to_code
                ),
                None,
            )
            if package_to_install is None:
                return False
            download_path = package_to_install.download()
            argostranslate.package.install_from_path(download_path)
            return True
        except Exception:
            return False

    def _get_translation(self, language_code: str) -> Optional[Any]:
        normalized = self._normalize_language_code(language_code)
        if not normalized or normalized == "en":
            return None
        if normalized in self._translation_cache:
            return self._translation_cache[normalized]

        from_lang = self._get_installed_language(normalized)
        to_lang = self._get_installed_language("en")

        if from_lang is None or to_lang is None:
            installed = self._install_language_pair(normalized, "en")
            if not installed:
                return None
            from_lang = self._get_installed_language(normalized)
            to_lang = self._get_installed_language("en")

        if from_lang is None or to_lang is None:
            return None

        try:
            translation = from_lang.get_translation(to_lang)
        except Exception:
            return None

        self._translation_cache[normalized] = translation
        return translation

    def translate_to_english(self, text: str, analyzer: Optional[NLTKTextAnalyzer] = None) -> TranslationResult:
        text = normalize_text(text)
        if text in self._cache:
            return self._cache[text]
        if not text:
            result = TranslationResult(text_en="", language="unknown", translated=False)
            self._cache[text] = result
            return result

        language = detect_language_safe(text)
        normalized_language = self._normalize_language_code(language) or "unknown"

        if normalized_language == "en":
            result = TranslationResult(text_en=text, language=normalized_language, translated=False)
            self._cache[text] = result
            return result

        translation = self._get_translation(normalized_language)
        if translation is not None:
            try:
                statements = split_statements(text, analyzer)
                translated_parts = []
                for statement in statements or [text]:
                    translated = normalize_text(translation.translate(statement))
                    if translated:
                        translated_parts.append(translated)
                translated_text = normalize_text(" ".join(translated_parts))
                result = TranslationResult(
                    text_en=translated_text or text,
                    language=normalized_language,
                    translated=bool(translated_text and translated_text != text),
                )
                self._cache[text] = result
                return result
            except Exception:
                pass

        result = TranslationResult(text_en=text, language=normalized_language, translated=False)
        self._cache[text] = result
        return result


def split_statements(text: str, analyzer: Optional[NLTKTextAnalyzer] = None) -> List[str]:
    text = normalize_text(text)
    if not text:
        return []
    if analyzer is not None:
        return analyzer.split_sentences(text)
    return [normalize_text(s) for s in SENTENCE_SPLIT_RE.split(text) if normalize_text(s)]


def contains_any(text: str, keywords: Iterable[str]) -> bool:
    low = f" {text.lower()} "
    for keyword in keywords:
        keyword_low = keyword.lower()
        if f" {keyword_low} " in low or keyword_low in low:
            return True
    return False


def infer_attributes(statement_en: str) -> List[str]:
    matched: List[str] = []
    low = statement_en.lower()
    for attribute, keywords in ATTRIBUTE_KEYWORDS.items():
        if contains_any(low, keywords):
            matched.append(attribute)
    if not matched:
        matched.append("general")
    return matched


def score_statement_sentiment(statement_en: str, analyzer: NLTKTextAnalyzer) -> Tuple[str, float, float]:
    normalized = normalize_text(statement_en)
    if not normalized:
        return "neutral", 0.0, 0.0

    scores = analyzer.vader_scores(normalized)
    compound = float(scores.get("compound", 0.0))

    if compound >= 0.05:
        return "positive", abs(compound), compound
    if compound <= -0.05:
        return "negative", abs(compound), compound
    return "neutral", 1.0 - abs(compound), compound


def extract_insights(original_text: str, english_text: str, analyzer: NLTKTextAnalyzer) -> List[Dict[str, Any]]:
    original_statements = split_statements(original_text, analyzer)
    english_statements = split_statements(english_text, analyzer)

    if not english_statements and original_statements:
        english_statements = original_statements
    if len(english_statements) < len(original_statements):
        english_statements.extend([""] * (len(original_statements) - len(english_statements)))
    elif len(original_statements) < len(english_statements):
        original_statements.extend([""] * (len(english_statements) - len(original_statements)))

    insights: List[Dict[str, Any]] = []
    for original_stmt, english_stmt in zip(original_statements, english_statements):
        stmt_en = normalize_text(english_stmt or original_stmt)
        stmt_original = normalize_text(original_stmt or english_stmt)
        if not stmt_en:
            continue

        sentiment_label, sentiment_score, raw_compound_score = score_statement_sentiment(stmt_en, analyzer)
        attributes = infer_attributes(stmt_en)
        insights.append(
            {
                "statement_original": stmt_original,
                "statement_english": stmt_en,
                "attributes": attributes,
                "sentiment_label": sentiment_label,
                "sentiment_score": sentiment_score,
                "raw_compound_score": raw_compound_score,
            }
        )
    return insights


def parse_product_payload(data: Dict[str, Any]) -> Tuple[str, List[Dict[str, Any]]]:
    if "product_name" in data and "webshops" in data:
        product_name = normalize_text(str(data.get("product_name", "")))
        webshops_raw = data.get("webshops") or {}
        if not isinstance(webshops_raw, dict):
            raise ValueError("webshops must be a JSON object")
        webshops: List[Dict[str, Any]] = []
        for webshop_key, webshop_data in webshops_raw.items():
            if not isinstance(webshop_data, dict):
                continue
            webshops.append(
                {
                    "name": normalize_text(str(webshop_key)) or infer_webshop_name(str(webshop_data.get("url", ""))),
                    "url": normalize_text(str(webshop_data.get("url", ""))),
                    "reviews": webshop_data.get("reviews") or [],
                }
            )
        return product_name, webshops

    product_name = normalize_text(str(data.get("title", "")))
    return product_name, [
        {
            "name": infer_webshop_name(str(data.get("url", ""))),
            "url": normalize_text(str(data.get("url", ""))),
            "reviews": data.get("reviews") or [],
        }
    ]


def collect_eligible_reviews(input_dir: Path) -> List[Tuple[str, str, str, str, Dict[str, Any]]]:
    collected: List[Tuple[str, str, str, str, Dict[str, Any]]] = []
    for json_path in sorted(input_dir.glob("*.json")):
        with json_path.open("r", encoding="latin1") as handle:
            data = json.load(handle)
        product_name, webshops = parse_product_payload(data)
        if not product_name:
            continue
        for webshop in webshops:
            webshop_name = webshop["name"]
            webshop_url = webshop["url"]
            reviews = webshop["reviews"] if isinstance(webshop.get("reviews"), list) else []
            for review in reviews:
                title = normalize_text(str(review.get("title", "")))
                body = normalize_text(str(review.get("body", "")))
                if has_review_description(title, body):
                    collected.append((json_path.name, product_name, webshop_name, webshop_url, review))
    return collected


def build_review_record(
    source_file: str,
    product_name: str,
    webshop_name: str,
    webshop_url: str,
    review: Dict[str, Any],
    translator: Translator,
    analyzer: NLTKTextAnalyzer,
) -> ReviewRecord:
    title_original = normalize_text(str(review.get("title", "")))
    body_original = normalize_text(str(review.get("body", "")))

    title_translation = translator.translate_to_english(title_original, analyzer) if title_original else TranslationResult("", "unknown", False)
    body_translation = translator.translate_to_english(body_original, analyzer) if body_original else TranslationResult("", "unknown", False)

    full_original_text = normalize_text(" ".join(part for part in [title_original, body_original] if part))
    full_english_text = normalize_text(" ".join(part for part in [title_translation.text_en, body_translation.text_en] if part))
    insights = extract_insights(full_original_text, full_english_text, analyzer)

    language_code = body_translation.language if body_original else title_translation.language
    was_translated = bool(title_translation.translated or body_translation.translated)

    return ReviewRecord(
        source_file=source_file,
        product_name=product_name,
        webshop_name=webshop_name,
        webshop_url=webshop_url,
        rating=parse_rating(str(review.get("rating", "")), webshop_name),
        review_date=parse_date(str(review.get("date", ""))),
        author=normalize_text(str(review.get("author", ""))),
        title_original=title_original,
        body_original=body_original,
        title_english=title_translation.text_en,
        body_english=body_translation.text_en,
        language_code=language_code,
        was_translated=was_translated,
        insights=insights,
    )


def write_csv(records: List[ReviewRecord], output_csv: Path) -> None:
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "source_file",
                "product_name",
                "webshop_name",
                "webshop_url",
                "rating",
                "review_date",
                "author",
                "title_original",
                "body_original",
                "title_english",
                "body_english",
                "language_code",
                "was_translated",
                "statement_original",
                "statement_english",
                "attributes",
                "sentiment_label",
                "sentiment_positive",
                "sentiment_neutral",
                "sentiment_negative",
                "sentiment_score",
                "raw_compound_score",
                "manual_sentence_rating",
            ],
        )
        writer.writeheader()
        for record in records:
            if not record.insights:
                writer.writerow(
                    {
                        "source_file": record.source_file,
                        "product_name": record.product_name,
                        "webshop_name": record.webshop_name,
                        "webshop_url": record.webshop_url,
                        "rating": record.rating,
                        "review_date": record.review_date,
                        "author": record.author,
                        "title_original": record.title_original,
                        "body_original": record.body_original,
                        "title_english": record.title_english,
                        "body_english": record.body_english,
                        "language_code": record.language_code,
                        "was_translated": int(record.was_translated),
                        "statement_original": "",
                        "statement_english": "",
                        "attributes": "",
                        "sentiment_label": "",
                        "sentiment_positive": 0,
                        "sentiment_neutral": 0,
                        "sentiment_negative": 0,
                        "sentiment_score": "",
                        "raw_compound_score": "",
                        "manual_sentence_rating": "",
                    }
                )
                continue

            for insight in record.insights:
                sentiment_label = str(insight.get("sentiment_label", ""))
                writer.writerow(
                    {
                        "source_file": record.source_file,
                        "product_name": record.product_name,
                        "webshop_name": record.webshop_name,
                        "webshop_url": record.webshop_url,
                        "rating": record.rating,
                        "review_date": record.review_date,
                        "author": record.author,
                        "title_original": record.title_original,
                        "body_original": record.body_original,
                        "title_english": record.title_english,
                        "body_english": record.body_english,
                        "language_code": record.language_code,
                        "was_translated": int(record.was_translated),
                        "statement_original": insight.get("statement_original", ""),
                        "statement_english": insight.get("statement_english", ""),
                        "attributes": "|".join(insight.get("attributes", [])),
                        "sentiment_label": sentiment_label,
                        "sentiment_positive": 1 if sentiment_label == "positive" else 0,
                        "sentiment_neutral": 1 if sentiment_label == "neutral" else 0,
                        "sentiment_negative": 1 if sentiment_label == "negative" else 0,
                        "sentiment_score": insight.get("sentiment_score", ""),
                        "raw_compound_score": insight.get("raw_compound_score", ""),
                        "manual_sentence_rating": "",
                    }
                )


def main() -> None:
    base_dir = Path(__file__).resolve().parent
    input_dir = (base_dir / "scraped_data").resolve()
    output_csv = (base_dir / "validationset.csv").resolve()
    sample_size = 100
    random_seed = 42

    if not input_dir.exists() or not input_dir.is_dir():
        raise SystemExit(f"Input directory does not exist or is not a directory: {input_dir}")

    eligible_reviews = collect_eligible_reviews(input_dir)
    if not eligible_reviews:
        raise SystemExit("No eligible reviews with descriptions were found.")

    sample_count = min(sample_size, len(eligible_reviews))
    rng = random.Random(random_seed)
    sampled = rng.sample(eligible_reviews, sample_count)

    translator = Translator()
    analyzer = NLTKTextAnalyzer()

    records: List[ReviewRecord] = []
    for source_file, product_name, webshop_name, webshop_url, review in sampled:
        records.append(
            build_review_record(
                source_file=source_file,
                product_name=product_name,
                webshop_name=webshop_name,
                webshop_url=webshop_url,
                review=review,
                translator=translator,
                analyzer=analyzer,
            )
        )

    write_csv(records, output_csv)
    print(f"Eligible reviews with descriptions: {len(eligible_reviews)}")
    print(f"Sampled reviews written: {len(records)}")
    print(f"CSV output: {output_csv}")


if __name__ == "__main__":
    main()
