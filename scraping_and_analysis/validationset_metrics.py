from __future__ import annotations

import argparse
import ast
from collections import Counter
from pathlib import Path
from typing import Dict, List, Sequence

import pandas as pd


VALID_SENTIMENTS = {"positive", "neutral", "negative"}
CLASS_ORDER = ["negative", "neutral", "positive"]
ORDINAL_VALUE = {label: idx for idx, label in enumerate(CLASS_ORDER)}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Analyze sentence-level review sentiment annotations and print evaluation metrics."
    )
    parser.add_argument(
        "csv_path",
        nargs="?",
        default="validationset.csv",
        help="Path to the sentence-level CSV exported by validationset_generator.py",
    )
    return parser.parse_args()


def normalize_text(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return "" if text.lower() == "nan" else text


def normalize_sentiment(value: object) -> str:
    text = normalize_text(value).lower()
    aliases = {
        "pos": "positive",
        "positive": "positive",
        "neu": "neutral",
        "neutral": "neutral",
        "neg": "negative",
        "negative": "negative",
    }
    return aliases.get(text, "")


def parse_attributes(value: object) -> List[str]:
    text = normalize_text(value)
    if not text:
        return []

    try:
        parsed = ast.literal_eval(text)
        if isinstance(parsed, list):
            return [normalize_text(item) for item in parsed if normalize_text(item)]
    except Exception:
        pass

    if "," in text:
        return [part.strip() for part in text.split(",") if part.strip()]

    return [text]


def pct(part: float, whole: float) -> float:
    return round((part / whole) * 100, 2) if whole else 0.0


def safe_div(numerator: float, denominator: float) -> float:
    return numerator / denominator if denominator else 0.0


def print_section(title: str) -> None:
    print(f"\n{title}")
    print("-" * len(title))


def print_counter(counter: Counter, total: int) -> None:
    if not counter:
        print("No data.")
        return
    for key, count in counter.most_common():
        print(f"{key}: {count} ({pct(count, total)}%)")


def build_confusion_matrix(y_true: Sequence[str], y_pred: Sequence[str], labels: Sequence[str]) -> pd.DataFrame:
    return pd.crosstab(
        pd.Categorical(y_true, categories=labels, ordered=True),
        pd.Categorical(y_pred, categories=labels, ordered=True),
        rownames=["manual"],
        colnames=["model"],
        dropna=False,
    )


def compute_per_class_metrics(confusion: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for label in confusion.index.tolist():
        tp = float(confusion.loc[label, label])
        fp = float(confusion[label].sum() - tp)
        fn = float(confusion.loc[label].sum() - tp)
        support = int(confusion.loc[label].sum())

        precision = safe_div(tp, tp + fp)
        recall = safe_div(tp, tp + fn)
        f1 = safe_div(2 * precision * recall, precision + recall)

        rows.append(
            {
                "label": label,
                "precision": precision,
                "recall": recall,
                "f1_score": f1,
                "support": support,
            }
        )

    return pd.DataFrame(rows).set_index("label")


def compute_summary_metrics(per_class: pd.DataFrame, confusion: pd.DataFrame) -> Dict[str, float]:
    total = int(confusion.to_numpy().sum())
    accuracy = safe_div(float(confusion.to_numpy().trace()), total)

    macro_precision = float(per_class["precision"].mean()) if not per_class.empty else 0.0
    macro_recall = float(per_class["recall"].mean()) if not per_class.empty else 0.0
    macro_f1 = float(per_class["f1_score"].mean()) if not per_class.empty else 0.0

    support_sum = float(per_class["support"].sum())
    weighted_precision = safe_div(float((per_class["precision"] * per_class["support"]).sum()), support_sum)
    weighted_recall = safe_div(float((per_class["recall"] * per_class["support"]).sum()), support_sum)
    weighted_f1 = safe_div(float((per_class["f1_score"] * per_class["support"]).sum()), support_sum)

    return {
        "accuracy": accuracy,
        "macro_precision": macro_precision,
        "macro_recall": macro_recall,
        "macro_f1": macro_f1,
        "weighted_precision": weighted_precision,
        "weighted_recall": weighted_recall,
        "weighted_f1": weighted_f1,
    }


def cohens_kappa_from_confusion(confusion: pd.DataFrame) -> float:
    total = float(confusion.to_numpy().sum())
    if total == 0:
        return 0.0
    observed = safe_div(float(confusion.to_numpy().trace()), total)
    row_marginals = confusion.sum(axis=1).astype(float)
    col_marginals = confusion.sum(axis=0).astype(float)
    expected = safe_div(float((row_marginals * col_marginals).sum()), total * total)
    if expected == 1.0:
        return 1.0
    return safe_div(observed - expected, 1.0 - expected)


def quadratic_weighted_kappa_from_confusion(confusion: pd.DataFrame) -> float:
    labels = confusion.index.tolist()
    k = len(labels)
    total = float(confusion.to_numpy().sum())
    if total == 0 or k <= 1:
        return 0.0

    observed = confusion.astype(float).to_numpy() / total
    row_hist = confusion.sum(axis=1).astype(float).to_numpy()
    col_hist = confusion.sum(axis=0).astype(float).to_numpy()
    expected = (row_hist[:, None] * col_hist[None, :]) / (total * total)

    denom = float((k - 1) ** 2)
    weights = [[((i - j) ** 2) / denom for j in range(k)] for i in range(k)]

    observed_weighted = sum(weights[i][j] * observed[i][j] for i in range(k) for j in range(k))
    expected_weighted = sum(weights[i][j] * expected[i][j] for i in range(k) for j in range(k))

    if expected_weighted == 0:
        return 1.0
    return 1.0 - (observed_weighted / expected_weighted)


def ordinal_error_metrics(y_true: Sequence[str], y_pred: Sequence[str]) -> Dict[str, float]:
    if not y_true:
        return {
            "mean_absolute_distance": 0.0,
            "mean_squared_error": 0.0,
            "off_by_one_rate": 0.0,
            "opposite_pole_error_rate": 0.0,
        }

    distances = [abs(ORDINAL_VALUE[t] - ORDINAL_VALUE[p]) for t, p in zip(y_true, y_pred)]
    total = len(distances)

    return {
        "mean_absolute_distance": sum(distances) / total,
        "mean_squared_error": sum(d * d for d in distances) / total,
        "off_by_one_rate": sum(1 for d in distances if d == 1) / total,
        "opposite_pole_error_rate": sum(1 for d in distances if d == 2) / total,
    }


def main() -> None:
    args = parse_args()
    csv_path = Path(args.csv_path)
    
    # If path is relative and doesn't exist, try looking in the script's directory
    if not csv_path.is_absolute() and not csv_path.exists():
        script_dir = Path(__file__).parent
        csv_path = script_dir / csv_path
    
    csv_path = csv_path.resolve()
    if not csv_path.exists():
        raise SystemExit(f"CSV file not found: {csv_path}")

    df = pd.read_csv(csv_path)

    required_columns = {
        "product_name",
        "statement_english",
        "attributes",
        "sentiment_label",
        "manual_sentence_rating",
    }
    missing = required_columns - set(df.columns)
    if missing:
        raise SystemExit(f"Missing required columns: {sorted(missing)}")

    df = df.copy()
    df["sentiment_label_clean"] = df["sentiment_label"].apply(normalize_sentiment)
    df["manual_sentence_rating_clean"] = df["manual_sentence_rating"].apply(normalize_sentiment)
    df["has_manual_rating"] = df["manual_sentence_rating_clean"].ne("")
    df["has_statement"] = df["statement_english"].apply(normalize_text).ne("")
    df["attribute_list"] = df["attributes"].apply(parse_attributes)
    df["review_key"] = (
        df.get("source_file", "").fillna("").astype(str)
        + " | "
        + df.get("product_name", "").fillna("").astype(str)
        + " | "
        + df.get("author", "").fillna("").astype(str)
        + " | "
        + df.get("review_date", "").fillna("").astype(str)
        + " | "
        + df.get("body_original", "").fillna("").astype(str)
    )

    total_rows = len(df)
    total_reviews = df["review_key"].nunique()
    total_products = df["product_name"].nunique()
    total_manual = int(df["has_manual_rating"].sum())

    print_section("Dataset overview")
    print(f"CSV: {csv_path}")
    print(f"Sentence-level rows: {total_rows}")
    print(f"Approx. unique reviews: {total_reviews}")
    print(f"Products: {total_products}")
    if "webshop_name" in df.columns:
        print(f"Webshops: {df['webshop_name'].nunique()}")
    print(f"Rows with non-empty statements: {int(df['has_statement'].sum())}")
    print(f"Rows with manual ratings: {total_manual}")

    print_section("Model sentiment distribution")
    print_counter(Counter(label for label in df["sentiment_label_clean"] if label), total_rows)

    print_section("Manual sentiment distribution")
    print_counter(Counter(label for label in df["manual_sentence_rating_clean"] if label), total_manual)

    print_section("Top attributes")
    attribute_counter: Counter = Counter()
    for attrs in df["attribute_list"]:
        attribute_counter.update(attrs)
    print_counter(attribute_counter, sum(attribute_counter.values()))

    comparable = df[(df["sentiment_label_clean"] != "") & (df["manual_sentence_rating_clean"] != "")].copy()
    if comparable.empty:
        print_section("Evaluation")
        print("No comparable rows found. Fill in 'manual_sentence_rating' with positive/neutral/negative first.")
        return

    y_true = comparable["manual_sentence_rating_clean"].tolist()
    y_pred = comparable["sentiment_label_clean"].tolist()
    confusion = build_confusion_matrix(y_true, y_pred, CLASS_ORDER)
    per_class = compute_per_class_metrics(confusion)
    summary = compute_summary_metrics(per_class, confusion)
    kappa = cohens_kappa_from_confusion(confusion)
    qwk = quadratic_weighted_kappa_from_confusion(confusion)
    ordinal = ordinal_error_metrics(y_true, y_pred)

    print_section("Overall classification metrics")
    print(f"Comparable rows: {len(comparable)}")
    print(f"Accuracy: {summary['accuracy']:.4f}")
    print(f"Macro precision: {summary['macro_precision']:.4f}")
    print(f"Macro recall: {summary['macro_recall']:.4f}")
    print(f"Macro F1-score: {summary['macro_f1']:.4f}")
    print(f"Weighted precision: {summary['weighted_precision']:.4f}")
    print(f"Weighted recall: {summary['weighted_recall']:.4f}")
    print(f"Weighted F1-score: {summary['weighted_f1']:.4f}")
    print(f"Cohen's kappa: {kappa:.4f}")
    print(f"Quadratic weighted kappa: {qwk:.4f}")

    print_section("Per-class metrics")
    printable_per_class = per_class.copy()
    for col in ["precision", "recall", "f1_score"]:
        printable_per_class[col] = printable_per_class[col].map(lambda x: round(float(x), 4))
    print(printable_per_class.to_string())

    print_section("Confusion matrix")
    print(confusion.to_string())

    print_section("Ordinal error metrics")
    print(f"Mean absolute distance: {ordinal['mean_absolute_distance']:.4f}")
    print(f"Mean squared error: {ordinal['mean_squared_error']:.4f}")
    print(f"Off-by-one rate: {ordinal['off_by_one_rate'] * 100:.2f}%")
    print(f"Opposite-pole error rate: {ordinal['opposite_pole_error_rate'] * 100:.2f}%")

    disagreements = comparable[comparable["manual_sentence_rating_clean"] != comparable["sentiment_label_clean"]].copy()
    if not disagreements.empty:
        disagreements["ordinal_distance"] = [
            abs(ORDINAL_VALUE[t] - ORDINAL_VALUE[p])
            for t, p in zip(
                disagreements["manual_sentence_rating_clean"],
                disagreements["sentiment_label_clean"],
            )
        ]

        print_section("Disagreement breakdown")
        pair_counter = Counter(
            zip(
                disagreements["manual_sentence_rating_clean"],
                disagreements["sentiment_label_clean"],
            )
        )
        for (manual_label, model_label), count in pair_counter.most_common():
            print(f"manual={manual_label}, model={model_label}: {count} ({pct(count, len(disagreements))}%)")

        print_section("Example disagreements (up to 10)")
        preview_cols = [
            col
            for col in [
                "product_name",
                "statement_original",
                "statement_english",
                "attributes",
                "manual_sentence_rating_clean",
                "sentiment_label_clean",
                "raw_compound_score",
                "ordinal_distance",
            ]
            if col in disagreements.columns
        ]
        for _, row in disagreements[preview_cols].head(10).iterrows():
            print(f"Product: {row.get('product_name', '')}")
            print(f"Statement: {row.get('statement_english', '')}")
            print(f"Attributes: {row.get('attributes', '')}")
            print(
                f"Manual={row.get('manual_sentence_rating_clean', '')} | "
                f"Model={row.get('sentiment_label_clean', '')} | "
                f"Compound={row.get('raw_compound_score', '')} | "
                f"Distance={row.get('ordinal_distance', '')}"
            )
            print()

    if "sentiment_score" in df.columns and "raw_compound_score" in df.columns:
        print_section("Score summary")
        print(df[["sentiment_score", "raw_compound_score"]].describe().round(4).to_string())


if __name__ == "__main__":
    main()
