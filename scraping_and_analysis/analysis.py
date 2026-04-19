from __future__ import annotations

import argparse
import json
import re
import sqlite3
import nltk
from dataclasses import dataclass
from datetime import datetime
from langdetect import detect
from nltk.sentiment import SentimentIntensityAnalyzer
from nltk.tokenize import sent_tokenize, word_tokenize
from pathlib import Path
import argostranslate.package
import argostranslate.translate
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
from urllib.parse import urlparse
import tempfile


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
NLTK_RESOURCES = (
    "punkt",
    "punkt_tab",
    "vader_lexicon",
)


@dataclass
class TranslationResult:
    text_en: str
    language: str
    translated: bool


@dataclass
class WebshopPayload:
    name: str
    url: str
    price_text: str
    review_count: int
    reviews: List[Dict[str, Any]]


@dataclass
class ProductPayload:
    product_name: str
    image_url: str
    specifications: Dict[str, Any]
    benchmarks: Dict[str, Any]
    price_text: str
    webshops: List[WebshopPayload]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import scraped product JSONs into SQLite.")
    parser.add_argument("--input-dir", default="scraped_data", help="Directory containing JSON files.")
    parser.add_argument("--db", default="reviews.sqlite", help="SQLite database path.")
    return parser.parse_args()


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def parse_price_to_amount(price_text: str) -> Optional[float]:
    if not price_text:
        return None
    # Find the first price number, handling both 123.45 and 123,45 formats
    m = re.search(r'(\d+(?:[.,]\d{2})?)', price_text.replace("€", "").replace("EUR", "").replace("$", "").replace("£", "").strip())
    if not m:
        return None
    price_str = m.group(1).replace(",", ".")
    try:
        return float(price_str)
    except ValueError:
        return None


def parse_rating(rating_text: str, webshop_name: str = "") -> Optional[float]:
    if not rating_text:
        return None
    m = re.search(r"(\d+(?:\.\d+)?)", rating_text)
    if not m:
        return None
    rating = float(m.group(1))
    # Scale MediaMarkt ratings from 0-5 to 0-10
    if webshop_name.lower() == "mediamarkt":
        rating *= 2
    return rating


def parse_date(date_text: str) -> Optional[str]:
    if not date_text:
        return None
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(date_text.strip(), fmt).date().isoformat()
        except ValueError:
            continue
    return None


def split_specifications_and_benchmarks(specifications: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    cleaned_specifications = dict(specifications or {})
    benchmarks = cleaned_specifications.pop("Benchmarks", {}) or {}

    if benchmarks and not isinstance(benchmarks, dict):
        benchmarks = {"raw": normalize_text(str(benchmarks))}

    return cleaned_specifications, benchmarks


def _parse_benchmark_int(text: str, label: str) -> Optional[int]:
    match = re.search(rf"{re.escape(label)}\s*:\s*([\d,.]+)", text, re.IGNORECASE)
    if not match:
        return None
    value_text = match.group(1).replace(",", "").replace(".", "")
    try:
        return int(value_text)
    except ValueError:
        return None


def _parse_benchmark_float(text: str, pattern: str) -> Optional[float]:
    match = re.search(pattern, text, re.IGNORECASE)
    if not match:
        return None
    value_text = match.group(1).replace(",", ".")
    try:
        return float(value_text)
    except ValueError:
        return None


def _parse_duration_hours(text: str) -> Optional[float]:
    match = re.search(r"(\d{1,2}):(\d{2})\s*h?", text, re.IGNORECASE)
    if not match:
        return None
    hours = int(match.group(1))
    minutes = int(match.group(2))
    return round(hours + (minutes / 60.0), 4)


def normalize_benchmarks(benchmarks: Dict[str, Any]) -> Dict[str, Any]:
    benchmark_map = benchmarks if isinstance(benchmarks, dict) else {}
    performance_text = normalize_text(str(benchmark_map.get("Performance", "")))
    display_text = normalize_text(str(benchmark_map.get("Display", "")))
    loudspeaker_text = normalize_text(str(benchmark_map.get("Loudspeaker", "")))
    battery_text = normalize_text(str(benchmark_map.get("Battery", "")))

    return {
        "performance_text": performance_text,
        "antutu_score": _parse_benchmark_int(performance_text, "AnTuTu"),
        "geekbench_score": _parse_benchmark_int(performance_text, "GeekBench"),
        "three_dmark_score": _parse_benchmark_int(performance_text, "3DMark"),
        "display_text": display_text,
        "display_brightness_nits": _parse_benchmark_float(display_text, r"([\d.]+)\s*nits"),
        "loudspeaker_text": loudspeaker_text,
        "loudspeaker_lufs": _parse_benchmark_float(loudspeaker_text, r"(-?[\d.]+)\s*LUFS"),
        "battery_text": battery_text,
        "battery_active_use_hours": _parse_duration_hours(battery_text),
        "raw_benchmarks_json": json.dumps(benchmark_map, ensure_ascii=False),
    }


def infer_webshop_name(url: str) -> str:
    domain = urlparse(url).netloc.lower()
    domain = domain.replace("www.", "")
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



def has_review_text(title: str, body: str) -> bool:
    return bool(normalize_text(title) or normalize_text(body))


def rating_to_weight(rating: Optional[float]) -> float:
    if rating is None:
        return 0.0
    if rating >= 9.0:
        return 1.0
    if rating >= 7.0:
        return 0.5
    if rating >= 5.0:
        return 0.0
    if rating >= 3.0:
        return -0.5
    return -1.0



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
        self._sia = SentimentIntensityAnalyzer() if SentimentIntensityAnalyzer else None

    def split_sentences(self, text: str) -> List[str]:
        normalized = normalize_text(text)
        if not normalized:
            return []
        if sent_tokenize is not None:
            try:
                return [normalize_text(s) for s in sent_tokenize(normalized) if normalize_text(s)]
            except LookupError:
                ensure_nltk_resources()
            except Exception:
                pass
        return [normalize_text(s) for s in SENTENCE_SPLIT_RE.split(normalized) if normalize_text(s)]

    def tokenize_words(self, text: str) -> List[str]:
        normalized = normalize_text(text).lower()
        if not normalized:
            return []
        if word_tokenize is not None:
            try:
                return [tok for tok in word_tokenize(normalized) if tok.strip()]
            except LookupError:
                ensure_nltk_resources()
            except Exception:
                pass
        return re.findall(r"\b[\w'-]+\b", normalized)

    def vader_scores(self, text: str) -> Dict[str, float]:
        if self._sia is None:
            return {"neg": 0.0, "neu": 1.0, "pos": 0.0, "compound": 0.0}
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
        return language_code.split('-')[0].lower()

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

    def translate_to_english(self, text: str) -> TranslationResult:
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
                statements = split_statements(text)
                translated_parts = []
                for statement in statements or [text]:
                    translated_part = normalize_text(translation.translate(statement))
                    if translated_part:
                        translated_parts.append(translated_part)
                translated = normalize_text(" ".join(translated_parts))
                result = TranslationResult(
                    text_en=translated or text,
                    language=normalized_language,
                    translated=bool(translated and translated != text),
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
    for kw in keywords:
        if f" {kw.lower()} " in low or kw.lower() in low:
            return True
    return False


def infer_attributes(statement_en: str) -> List[str]:
    matched = []
    low = statement_en.lower()
    for attribute, keywords in ATTRIBUTE_KEYWORDS.items():
        if contains_any(low, keywords):
            matched.append(attribute)
    if not matched:
        matched.append("general")
    return matched


def score_statement_sentiment(statement_en: str, analyzer: Optional[NLTKTextAnalyzer] = None) -> Tuple[str, float, float]:
    normalized = normalize_text(statement_en)
    if not normalized:
        return "neutral", 0.0, 0.0

    scores = analyzer.vader_scores(normalized) if analyzer is not None else {"neg": 0.0, "neu": 1.0, "pos": 0.0, "compound": 0.0}
    compound = float(scores.get("compound", 0.0))

    if compound >= 0.05:
        return "positive", abs(compound), compound
    if compound <= -0.05:
        return "negative", abs(compound), compound
    return "neutral", 1.0 - abs(compound), compound

def ensure_column_exists(conn: sqlite3.Connection, table_name: str, column_name: str, definition_sql: str) -> None:
    existing = {row[1] for row in conn.execute(f"PRAGMA table_info({table_name})")}
    if column_name not in existing:
        conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition_sql}")


def create_reviews_schema(conn: sqlite3.Connection) -> None:
    """Create schema for temporary reviews database."""
    conn.executescript(
        """
        PRAGMA foreign_keys = ON;

        CREATE TABLE IF NOT EXISTS webshops (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            domain TEXT NOT NULL UNIQUE,
            review_count INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            webshop_id INTEGER NOT NULL,
            rating REAL,
            review_date TEXT,
            title_original TEXT,
            body_original TEXT,
            title_english TEXT,
            body_english TEXT,
            language_code TEXT,
            was_translated INTEGER NOT NULL DEFAULT 0,
            author TEXT,
            verified INTEGER,
            source_page INTEGER,
            source_index_on_page INTEGER,
            variant TEXT,
            raw_review_json TEXT NOT NULL,
            UNIQUE(product_id, webshop_id, author, review_date, source_page, source_index_on_page, rating, title_original, body_original),
            FOREIGN KEY (webshop_id) REFERENCES webshops(id)
        );

        CREATE INDEX IF NOT EXISTS idx_reviews_product_id ON reviews(product_id);
        CREATE INDEX IF NOT EXISTS idx_reviews_webshop_id ON reviews(webshop_id);
        """
    )
    conn.commit()


def create_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        PRAGMA foreign_keys = ON;

        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE
        );

        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            image_url TEXT,
            price_text TEXT,
            price_amount REAL,
            specifications_json TEXT NOT NULL,
            average_rating REAL,
            source_file TEXT,
            UNIQUE(name, source_file),
            FOREIGN KEY (category_id) REFERENCES categories(id)
        );

        CREATE TABLE IF NOT EXISTS product_benchmarks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL UNIQUE,
            performance_text TEXT,
            antutu_score INTEGER,
            geekbench_score INTEGER,
            three_dmark_score INTEGER,
            display_text TEXT,
            display_brightness_nits REAL,
            loudspeaker_text TEXT,
            loudspeaker_lufs REAL,
            battery_text TEXT,
            battery_active_use_hours REAL,
            raw_benchmarks_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS product_webshops (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            webshop_id INTEGER NOT NULL,
            webshop_name TEXT,
            product_url TEXT NOT NULL,
            price_eur REAL DEFAULT 0,
            review_count INTEGER DEFAULT 0,
            UNIQUE(product_id, webshop_id, product_url),
            FOREIGN KEY (product_id) REFERENCES products(id)
        );

        CREATE TABLE IF NOT EXISTS attribute_statements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            review_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            attribute_name TEXT NOT NULL,
            sentiment_label TEXT NOT NULL CHECK (sentiment_label IN ('positive','neutral','negative')),
            sentiment_score REAL,
            raw_compound_score REAL,
            review_rating REAL,
            rating_weight REAL NOT NULL DEFAULT 0,
            weighted_sentiment_score REAL NOT NULL DEFAULT 0,
            statement_original TEXT NOT NULL,
            statement_english TEXT NOT NULL,
            review_timestamp TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (product_id) REFERENCES products(id)
        );

        CREATE INDEX IF NOT EXISTS idx_product_benchmarks_product_id ON product_benchmarks(product_id);
        CREATE INDEX IF NOT EXISTS idx_attr_product_attribute ON attribute_statements(product_id, attribute_name);
        CREATE INDEX IF NOT EXISTS idx_attr_review_timestamp ON attribute_statements(review_timestamp);
        """
    )
    ensure_column_exists(conn, "products", "image_url", "TEXT")
    ensure_column_exists(conn, "product_benchmarks", "performance_text", "TEXT")
    ensure_column_exists(conn, "product_benchmarks", "antutu_score", "INTEGER")
    ensure_column_exists(conn, "product_benchmarks", "geekbench_score", "INTEGER")
    ensure_column_exists(conn, "product_benchmarks", "three_dmark_score", "INTEGER")
    ensure_column_exists(conn, "product_benchmarks", "display_text", "TEXT")
    ensure_column_exists(conn, "product_benchmarks", "display_brightness_nits", "REAL")
    ensure_column_exists(conn, "product_benchmarks", "loudspeaker_text", "TEXT")
    ensure_column_exists(conn, "product_benchmarks", "loudspeaker_lufs", "REAL")
    ensure_column_exists(conn, "product_benchmarks", "battery_text", "TEXT")
    ensure_column_exists(conn, "product_benchmarks", "battery_active_use_hours", "REAL")
    ensure_column_exists(conn, "product_benchmarks", "raw_benchmarks_json", "TEXT NOT NULL DEFAULT '{}'")
    ensure_column_exists(conn, "product_benchmarks", "updated_at", "TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP")
    ensure_column_exists(conn, "product_webshops", "webshop_name", "TEXT")
    ensure_column_exists(conn, "product_webshops", "price_eur", "REAL DEFAULT 0")
    ensure_column_exists(conn, "product_webshops", "review_count", "INTEGER DEFAULT 0")
    ensure_column_exists(conn, "attribute_statements", "raw_compound_score", "REAL")
    ensure_column_exists(conn, "attribute_statements", "review_rating", "REAL")
    ensure_column_exists(conn, "attribute_statements", "rating_weight", "REAL NOT NULL DEFAULT 0")
    ensure_column_exists(conn, "attribute_statements", "weighted_sentiment_score", "REAL NOT NULL DEFAULT 0")

    conn.executescript(
        """
        CREATE VIEW IF NOT EXISTS attribute_sentiment_summary AS
        SELECT
            product_id,
            attribute_name,
            COUNT(*) AS mention_count,
            SUM(CASE WHEN sentiment_label = 'positive' THEN 1 ELSE 0 END) AS positive_count,
            SUM(CASE WHEN sentiment_label = 'negative' THEN 1 ELSE 0 END) AS negative_count,
            SUM(CASE WHEN sentiment_label = 'neutral' THEN 1 ELSE 0 END) AS neutral_count,
            ROUND(100.0 * SUM(CASE WHEN sentiment_label = 'positive' THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 2) AS positive_pct,
            ROUND(100.0 * SUM(CASE WHEN sentiment_label = 'negative' THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 2) AS negative_pct,
            ROUND(100.0 * SUM(CASE WHEN sentiment_label = 'neutral' THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 2) AS neutral_pct,
            ROUND(SUM(weighted_sentiment_score), 4) AS weighted_net_sentiment,
            ROUND(AVG(weighted_sentiment_score), 4) AS weighted_avg_sentiment,
            ROUND(100.0 * SUM(CASE WHEN weighted_sentiment_score > 0 THEN ABS(weighted_sentiment_score) ELSE 0 END) / NULLIF(SUM(ABS(weighted_sentiment_score)), 0), 2) AS weighted_positive_pct,
            ROUND(100.0 * SUM(CASE WHEN weighted_sentiment_score < 0 THEN ABS(weighted_sentiment_score) ELSE 0 END) / NULLIF(SUM(ABS(weighted_sentiment_score)), 0), 2) AS weighted_negative_pct
        FROM attribute_statements
        GROUP BY product_id, attribute_name;
        """
    )
    conn.commit()


def get_or_create_category(conn: sqlite3.Connection, name: str) -> int:
    conn.execute("INSERT OR IGNORE INTO categories(name) VALUES (?)", (name,))
    row = conn.execute("SELECT id FROM categories WHERE name = ?", (name,)).fetchone()
    assert row is not None
    return int(row[0])


def upsert_product(
    conn: sqlite3.Connection,
    category_id: int,
    name: str,
    image_url: str,
    price_text: str,
    price_amount: Optional[float],
    specifications_json: str,
    average_rating: Optional[float],
    source_file: str,
) -> int:
    conn.execute(
        """
        INSERT INTO products (
            category_id, name, image_url, price_text, price_amount,
            specifications_json, average_rating, source_file
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(name, source_file) DO UPDATE SET
            category_id = excluded.category_id,
            image_url = excluded.image_url,
            price_text = excluded.price_text,
            price_amount = excluded.price_amount,
            specifications_json = excluded.specifications_json,
            average_rating = excluded.average_rating
        """,
        (category_id, name, image_url, price_text, price_amount, specifications_json, average_rating, source_file),
    )
    row = conn.execute(
        "SELECT id FROM products WHERE name = ? AND source_file = ?",
        (name, source_file),
    ).fetchone()
    assert row is not None
    return int(row[0])


def upsert_product_benchmarks(conn: sqlite3.Connection, product_id: int, benchmarks: Dict[str, Any]) -> None:
    normalized = normalize_benchmarks(benchmarks)
    conn.execute(
        """
        INSERT INTO product_benchmarks (
            product_id, performance_text, antutu_score, geekbench_score, three_dmark_score,
            display_text, display_brightness_nits, loudspeaker_text, loudspeaker_lufs,
            battery_text, battery_active_use_hours, raw_benchmarks_json, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(product_id) DO UPDATE SET
            performance_text = excluded.performance_text,
            antutu_score = excluded.antutu_score,
            geekbench_score = excluded.geekbench_score,
            three_dmark_score = excluded.three_dmark_score,
            display_text = excluded.display_text,
            display_brightness_nits = excluded.display_brightness_nits,
            loudspeaker_text = excluded.loudspeaker_text,
            loudspeaker_lufs = excluded.loudspeaker_lufs,
            battery_text = excluded.battery_text,
            battery_active_use_hours = excluded.battery_active_use_hours,
            raw_benchmarks_json = excluded.raw_benchmarks_json,
            updated_at = CURRENT_TIMESTAMP
        """,
        (
            product_id,
            normalized["performance_text"],
            normalized["antutu_score"],
            normalized["geekbench_score"],
            normalized["three_dmark_score"],
            normalized["display_text"],
            normalized["display_brightness_nits"],
            normalized["loudspeaker_text"],
            normalized["loudspeaker_lufs"],
            normalized["battery_text"],
            normalized["battery_active_use_hours"],
            normalized["raw_benchmarks_json"],
        ),
    )


def upsert_webshop(conn: sqlite3.Connection, name: str, domain: str, review_count: int) -> int:
    conn.execute(
        """
        INSERT INTO webshops (name, domain, review_count)
        VALUES (?, ?, ?)
        ON CONFLICT(domain) DO UPDATE SET
            name = excluded.name,
            review_count = excluded.review_count
        """,
        (name, domain, review_count),
    )
    row = conn.execute("SELECT id FROM webshops WHERE domain = ?", (domain,)).fetchone()
    assert row is not None
    return int(row[0])


def link_product_webshop(
    conn: sqlite3.Connection,
    product_id: int,
    webshop_id: int,
    webshop_name: str,
    product_url: str,
    price_eur: Optional[float],
    review_count: int,
) -> None:
    conn.execute(
        """
        INSERT OR IGNORE INTO product_webshops (
            product_id, webshop_id, webshop_name, product_url, price_eur, review_count
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (product_id, webshop_id, webshop_name, product_url, price_eur or 0.0, review_count),
    )


def insert_review(
    conn_reviews: sqlite3.Connection,
    product_id: int,
    webshop_id: int,
    review: Dict[str, Any],
    title_en: str,
    body_en: str,
    language_code: str,
    was_translated: bool,
    webshop_name: str,
) -> int:
    conn_reviews.execute(
        """
        INSERT OR IGNORE INTO reviews (
            product_id, webshop_id, rating, review_date,
            title_original, body_original, title_english, body_english,
            language_code, was_translated, author, verified,
            source_page, source_index_on_page, variant, raw_review_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            product_id,
            webshop_id,
            parse_rating(str(review.get("rating", "")), webshop_name),
            parse_date(str(review.get("date", ""))),
            normalize_text(str(review.get("title", ""))),
            normalize_text(str(review.get("body", ""))),
            title_en,
            body_en,
            language_code,
            1 if was_translated else 0,
            normalize_text(str(review.get("author", ""))),
            1 if str(review.get("verified", "")).lower() == "true" else 0,
            int(review.get("page")) if str(review.get("page", "")).isdigit() else None,
            int(review.get("index_on_page")) if str(review.get("index_on_page", "")).isdigit() else None,
            normalize_text(str(review.get("variant", ""))),
            json.dumps(review, ensure_ascii=False),
        ),
    )
    row = conn_reviews.execute(
        """
        SELECT id
        FROM reviews
        WHERE product_id = ?
          AND webshop_id = ?
          AND COALESCE(author, '') = COALESCE(?, '')
          AND COALESCE(review_date, '') = COALESCE(?, '')
          AND COALESCE(source_page, -1) = COALESCE(?, -1)
          AND COALESCE(source_index_on_page, -1) = COALESCE(?, -1)
          AND COALESCE(rating, -1) = COALESCE(?, -1)
          AND COALESCE(title_original, '') = COALESCE(?, '')
          AND COALESCE(body_original, '') = COALESCE(?, '')
        """,
        (
            product_id,
            webshop_id,
            normalize_text(str(review.get("author", ""))),
            parse_date(str(review.get("date", ""))),
            int(review.get("page")) if str(review.get("page", "")).isdigit() else None,
            int(review.get("index_on_page")) if str(review.get("index_on_page", "")).isdigit() else None,
            parse_rating(str(review.get("rating", "")), webshop_name),
            normalize_text(str(review.get("title", ""))),
            normalize_text(str(review.get("body", ""))),
        ),
    ).fetchone()
    assert row is not None
    return int(row[0])


def insert_attribute_statements(
    conn: sqlite3.Connection,
    review_id: int,
    product_id: int,
    review_timestamp: Optional[str],
    original_text: str,
    english_text: str,
    review_rating: Optional[float],
    analyzer: Optional[NLTKTextAnalyzer] = None,
) -> int:
    original_statements = split_statements(original_text, analyzer)
    english_statements = split_statements(english_text, analyzer)

    if not english_statements and original_statements:
        english_statements = original_statements
    if len(english_statements) < len(original_statements):
        english_statements.extend([""] * (len(original_statements) - len(english_statements)))
    elif len(original_statements) < len(english_statements):
        original_statements.extend([""] * (len(english_statements) - len(original_statements)))

    count = 0
    for original_stmt, english_stmt in zip(original_statements, english_statements):
        stmt_en = normalize_text(english_stmt or original_stmt)
        stmt_original = normalize_text(original_stmt or english_stmt)
        if not stmt_en:
            continue

        sentiment_label, sentiment_score, raw_compound_score = score_statement_sentiment(stmt_en, analyzer)
        rating_weight = rating_to_weight(review_rating)
        weighted_sentiment_score = raw_compound_score * rating_weight
        attributes = infer_attributes(stmt_en)

        for attribute_name in attributes:
            conn.execute(
                """
                INSERT INTO attribute_statements (
                    review_id, product_id, attribute_name, sentiment_label, sentiment_score,
                    raw_compound_score, review_rating, rating_weight, weighted_sentiment_score,
                    statement_original, statement_english, review_timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    review_id,
                    product_id,
                    attribute_name,
                    sentiment_label,
                    sentiment_score,
                    raw_compound_score,
                    review_rating,
                    rating_weight,
                    weighted_sentiment_score,
                    stmt_original,
                    stmt_en,
                    review_timestamp,
                ),
            )
            count += 1
    return count


def extract_product_price_text(new_schema_data: Dict[str, Any], webshops: List[WebshopPayload]) -> str:
    prices = []
    gsmarena_price = normalize_text(
        str((((new_schema_data.get("gsmarena") or {}).get("specs") or {}).get("Misc") or {}).get("Price", ""))
    )
    if gsmarena_price:
        amount = parse_price_to_amount(gsmarena_price)
        if amount is not None:
            prices.append((amount, gsmarena_price))

    mediamarkt_price = None
    for webshop in webshops:
        if webshop.price_text:
            amount = parse_price_to_amount(webshop.price_text)
            if amount is not None:
                prices.append((amount, webshop.price_text))
                if webshop.name and "mediamarkt" in webshop.name.lower():
                    mediamarkt_price = webshop.price_text

    if mediamarkt_price:
        return mediamarkt_price

    if webshops:
        # fallback to first webshop price if available
        first_price = next((ws.price_text for ws in webshops if ws.price_text), None)
        if first_price:
            return first_price

    if prices:
        # fallback to the lowest listing price
        min_price = min(prices, key=lambda x: x[0])
        return min_price[1]

    return ""


def parse_new_schema(data: Dict[str, Any]) -> ProductPayload:
    product_name = normalize_text(str(data.get("product_name", "")))
    gsmarena = data.get("gsmarena") or {}
    image_url = normalize_text(str(gsmarena.get("image_url", "")))
    specifications = gsmarena.get("specs") or {}
    if not isinstance(specifications, dict):
        raise ValueError("gsmarena.specs must be a JSON object")
    specifications, benchmarks = split_specifications_and_benchmarks(specifications)

    webshops_raw = data.get("webshops") or {}
    if not isinstance(webshops_raw, dict):
        raise ValueError("webshops must be a JSON object")

    webshops: List[WebshopPayload] = []
    for webshop_key, webshop_data in webshops_raw.items():
        if not isinstance(webshop_data, dict):
            continue
        reviews = webshop_data.get("reviews") or []
        if not isinstance(reviews, list):
            raise ValueError(f"webshops.{webshop_key}.reviews must be a JSON array")
        url = normalize_text(str(webshop_data.get("url", "")))
        webshops.append(
            WebshopPayload(
                name=normalize_text(str(webshop_key)) or infer_webshop_name(url),
                url=url,
                price_text=normalize_text(str(webshop_data.get("price", ""))),
                review_count=int(webshop_data.get("review_count", 0) or 0),
                reviews=reviews,
            )
        )

    return ProductPayload(
        product_name=product_name,
        image_url=image_url,
        specifications=specifications,
        benchmarks=benchmarks,
        price_text=extract_product_price_text(data, webshops),
        webshops=webshops,
    )


def parse_legacy_schema(data: Dict[str, Any]) -> ProductPayload:
    url = normalize_text(str(data.get("url", "")))
    title = normalize_text(str(data.get("title", "")))
    price_text = normalize_text(str(data.get("price", "")))
    specifications = data.get("specifications", {}) or {}
    reviews = data.get("reviews", []) or []

    if not isinstance(specifications, dict):
        raise ValueError("specifications must be a JSON object")
    if not isinstance(reviews, list):
        raise ValueError("reviews must be a JSON array")
    specifications, benchmarks = split_specifications_and_benchmarks(specifications)

    return ProductPayload(
        product_name=title,
        image_url=normalize_text(str(data.get("image_url", ""))),
        specifications=specifications,
        benchmarks=benchmarks,
        price_text=price_text,
        webshops=[
            WebshopPayload(
                name=infer_webshop_name(url),
                url=url,
                price_text=price_text,
                review_count=len(reviews),
                reviews=reviews,
            )
        ],
    )


def parse_product_payload(data: Dict[str, Any]) -> ProductPayload:
    if "product_name" in data and "gsmarena" in data and "webshops" in data:
        payload = parse_new_schema(data)
    else:
        payload = parse_legacy_schema(data)

    if not payload.product_name:
        raise ValueError("Could not determine product name")
    return payload


def process_json_file(
    conn: sqlite3.Connection,
    conn_reviews: sqlite3.Connection,
    translator: Translator,
    analyzer: NLTKTextAnalyzer,
    json_path: Path,
    category_id: int,
) -> Dict[str, Any]:
    with json_path.open("r", encoding="latin1") as f:
        data = json.load(f)

    payload = parse_product_payload(data)

    all_ratings = [
        parse_rating(str(review.get("rating", "")), webshop.name or infer_webshop_name(webshop.url))
        for webshop in payload.webshops
        for review in webshop.reviews
    ]
    all_ratings = [rating for rating in all_ratings if rating is not None]
    average_rating = (sum(all_ratings) / len(all_ratings)) if all_ratings else None

    product_id = upsert_product(
        conn=conn,
        category_id=category_id,
        name=payload.product_name,
        image_url=payload.image_url,
        price_text=payload.price_text,
        price_amount=parse_price_to_amount(payload.price_text),
        specifications_json=json.dumps(payload.specifications, ensure_ascii=False),
        average_rating=average_rating,
        source_file=json_path.name,
    )
    upsert_product_benchmarks(conn, product_id, payload.benchmarks)

    inserted_reviews = 0
    inserted_attribute_statements = 0
    total_review_count = 0
    webshop_ids: List[int] = []

    for webshop in payload.webshops:
        domain = urlparse(webshop.url).netloc.lower().replace("www.", "")
        webshop_name = webshop.name or infer_webshop_name(webshop.url)
        total_review_count += webshop.review_count or len(webshop.reviews)

        webshop_id = upsert_webshop(
            conn=conn_reviews,
            name=webshop_name,
            domain=domain or webshop_name.lower().replace(" ", "-") or "unknown",
            review_count=webshop.review_count or len(webshop.reviews),
        )
        webshop_ids.append(webshop_id)

        if webshop.url:
            link_product_webshop(
                conn,
                product_id,
                webshop_id,
                webshop_name,
                webshop.url,
                parse_price_to_amount(webshop.price_text),
                webshop.review_count or len(webshop.reviews),
            )

        for review in webshop.reviews:
            title_original = normalize_text(str(review.get("title", "")))
            body_original = normalize_text(str(review.get("body", "")))

            title_translation = translator.translate_to_english(title_original) if title_original else TranslationResult("", "unknown", False)
            body_translation = translator.translate_to_english(body_original) if body_original else TranslationResult("", "unknown", False)

            language_code = body_translation.language if body_original else title_translation.language
            was_translated = bool(title_translation.translated or body_translation.translated)

            review_rating = parse_rating(str(review.get("rating", "")), webshop_name)

            review_id = insert_review(
                conn_reviews=conn_reviews,
                product_id=product_id,
                webshop_id=webshop_id,
                review=review,
                title_en=title_translation.text_en,
                body_en=body_translation.text_en,
                language_code=language_code,
                was_translated=was_translated,
                webshop_name=webshop_name,
            )
            inserted_reviews += 1

            if not has_review_text(title_original, body_original):
                continue

            review_timestamp = parse_date(str(review.get("date", "")))

            full_original_text = normalize_text(" ".join(p for p in [title_original, body_original] if p))
            full_english_text = normalize_text(" ".join(p for p in [title_translation.text_en, body_translation.text_en] if p))

            if full_original_text or full_english_text:
                inserted_attribute_statements += insert_attribute_statements(
                    conn=conn,
                    review_id=review_id,
                    product_id=product_id,
                    review_timestamp=review_timestamp,
                    original_text=full_original_text,
                    english_text=full_english_text,
                    review_rating=review_rating,
                    analyzer=analyzer,
                )

    conn.commit()
    conn_reviews.commit()

    return {
        "file": json_path.name,
        "product_id": product_id,
        "webshop_ids": webshop_ids,
        "product_name": payload.product_name,
        "image_url": payload.image_url,
        "review_count": total_review_count,
        "average_rating": average_rating,
        "attribute_statements": inserted_attribute_statements,
    }


def main() -> None:
    BASE_DIR = Path(__file__).resolve().parent

    input_dir = (BASE_DIR / "scraped_data").resolve()
    db_path = (BASE_DIR.parent / "public" / "reviews.db").resolve()

    if not input_dir.exists() or not input_dir.is_dir():
        raise SystemExit(f"Input directory does not exist or is not a directory: {input_dir}")

    json_files = sorted(input_dir.glob("*.json"))
    if not json_files:
        raise SystemExit(f"No JSON files found in: {input_dir}")

    db_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Create main database for analysis results
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    create_schema(conn)
    
    # Create temporary database for reviews
    temp_dir = tempfile.mkdtemp()
    reviews_db_path = Path(temp_dir) / "reviews_temp.db"
    conn_reviews = sqlite3.connect(str(reviews_db_path))
    conn_reviews.row_factory = sqlite3.Row
    create_reviews_schema(conn_reviews)
    
    category_id = get_or_create_category(conn, "Smartphones")
    translator = Translator()
    analyzer = NLTKTextAnalyzer()

    summaries = []
    try:
        for json_file in json_files:
            summary = process_json_file(conn, conn_reviews, translator, analyzer, json_file, category_id)
            summaries.append(summary)
            print(
                f"[OK] {summary['file']}: "
                f"product={summary['product_name']}, "
                f"reviews={summary['review_count']}, "
                f"avg_rating={summary['average_rating']}, "
                f"attribute_statements={summary['attribute_statements']}"
            )

        print("\nFinished.")
        print(f"Main Database: {db_path.resolve()}")
        print(f"Files processed successfully: {len(summaries)}/{len(json_files)}")

        product_count = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
        attr_count = conn.execute("SELECT COUNT(*) FROM attribute_statements").fetchone()[0]

        print(f"Products: {product_count}")
        print(f"Attribute statements: {attr_count}")
    
    finally:
        conn.close()
        conn_reviews.close()
        
        # Delete temporary reviews database
        if reviews_db_path.exists():
            reviews_db_path.unlink()
            print(f"Temporary reviews database deleted: {reviews_db_path}")


if __name__ == "__main__":
    main()
