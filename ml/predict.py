"""
predict.py — Predict top 3 diseases from symptom names using the trained model.

Standalone module (no Flask). Loads artifacts saved by train_model.py.
"""

import argparse
import os
import re
import sys
from typing import List, Tuple

import joblib
import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODELS_DIR = os.path.join(BASE_DIR, "models")
MODEL_PATH = os.path.join(MODELS_DIR, "disease_model.pkl")
FEATURE_NAMES_PATH = os.path.join(MODELS_DIR, "feature_names.pkl")
LABEL_ENCODER_PATH = os.path.join(MODELS_DIR, "label_encoder.pkl")

TOP_K = 3


def normalize_symptom_name(name: str) -> str:
    """
    Normalize symptom text so user input matches CSV column names.

    Examples:
        "Skin Rash"      → "skin_rash"
        "skin_rash"      → "skin_rash"
        "spotting urination" → "spotting_urination" (matches "spotting_ urination" in CSV)
    """
    cleaned = name.strip().lower().replace(" ", "_")
    cleaned = re.sub(r"_+", "_", cleaned)
    return cleaned.strip("_")


def load_artifacts():
    """Load model, symptom column order, and label encoder from disk."""
    missing = []
    for path in (MODEL_PATH, FEATURE_NAMES_PATH, LABEL_ENCODER_PATH):
        if not os.path.isfile(path):
            missing.append(path)

    if missing:
        raise FileNotFoundError(
            "Missing model artifacts:\n  "
            + "\n  ".join(missing)
            + "\nRun training first: python train_model.py"
        )

    model = joblib.load(MODEL_PATH)
    feature_names = joblib.load(FEATURE_NAMES_PATH)
    label_encoder = joblib.load(LABEL_ENCODER_PATH)

    if not feature_names:
        raise ValueError("feature_names.pkl is empty — retrain the model.")

    return model, feature_names, label_encoder


def symptoms_to_feature_vector(symptoms: List[str], feature_names: List[str]) -> np.ndarray:
    """
    Convert symptom names into one row of 0/1 values matching training columns.

    The model was trained on 132 columns like itching, skin_rash, high_fever, ...
    For each column: 1 if the patient has that symptom, else 0.
    """
    normalized_input = {normalize_symptom_name(s) for s in symptoms if s.strip()}
    canonical_lookup = {normalize_symptom_name(f): f for f in feature_names}

    row = []
    for feature in feature_names:
        key = normalize_symptom_name(feature)
        row.append(1 if key in normalized_input else 0)

    return np.array(row).reshape(1, -1)


def find_unknown_symptoms(symptoms: List[str], feature_names: List[str]) -> List[str]:
    """Symptoms that do not match any trained column name."""
    known = {normalize_symptom_name(f) for f in feature_names}
    unknown = []
    for symptom in symptoms:
        if not symptom.strip():
            continue
        if normalize_symptom_name(symptom) not in known:
            unknown.append(symptom.strip())
    return unknown


def predict_top_diseases(
    symptoms: List[str],
    top_k: int = TOP_K,
) -> List[Tuple[str, float]]:
    """
    Return top_k (disease, confidence_percent) pairs.

    Confidence calculation:
        Random Forest's predict_proba() returns, for each disease class,
        the fraction of trees that voted for that class.
        Example: 0.73 → 73% confidence.
    """
    if not symptoms or all(not s.strip() for s in symptoms):
        raise ValueError("Please provide at least one symptom name.")

    model, feature_names, label_encoder = load_artifacts()

    for name in find_unknown_symptoms(symptoms, feature_names):
        print(
            f"Warning: symptom '{name}' is not in the training dataset — ignored.",
            file=sys.stderr,
        )

    feature_vector = symptoms_to_feature_vector(symptoms, feature_names)
    feature_df = pd.DataFrame(feature_vector, columns=feature_names)

    if feature_vector.sum() == 0:
        raise ValueError(
            "None of the provided symptoms match known features. "
            "Use names like: itching, skin_rash, high_fever, cough"
        )

    probabilities = model.predict_proba(feature_df)[0]
    encoded_classes = model.classes_

    ranked = sorted(
        zip(encoded_classes, probabilities),
        key=lambda item: item[1],
        reverse=True,
    )

    top_k = min(top_k, len(ranked))
    results = []
    for encoded_label, prob in ranked[:top_k]:
        disease_name = label_encoder.inverse_transform([int(encoded_label)])[0]
        confidence_percent = round(float(prob) * 100, 2)
        results.append((disease_name, confidence_percent))

    return results


def format_predictions(predictions: List[Tuple[str, float]]) -> str:
    lines = ["Top disease predictions:", "-" * 40]
    for rank, (disease, confidence) in enumerate(predictions, start=1):
        lines.append(f"  {rank}. {disease} - {confidence}% confidence")
    return "\n".join(lines)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Predict top 3 diseases from Kaggle symptom names.",
        epilog=(
            "Examples:\n"
            "  python predict.py itching skin_rash\n"
            "  python predict.py --symptoms itching,skin_rash,continuous_sneezing"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "symptoms_positional",
        nargs="*",
        help="Symptom names (e.g. itching skin_rash high_fever)",
    )
    parser.add_argument(
        "--symptoms",
        "-s",
        type=str,
        default="",
        help="Comma-separated symptoms (e.g. itching,skin_rash,cough)",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=TOP_K,
        help=f"Number of predictions to return (default: {TOP_K})",
    )
    return parser.parse_args()


def collect_symptoms_from_args(args) -> List[str]:
    collected = list(args.symptoms_positional)
    if args.symptoms:
        collected.extend(part.strip() for part in args.symptoms.split(",") if part.strip())
    return collected


def main() -> int:
    try:
        args = parse_args()
        if args.top < 1:
            raise ValueError("--top must be at least 1.")

        predictions = predict_top_diseases(collect_symptoms_from_args(args), top_k=args.top)
        print(format_predictions(predictions))
        return 0

    except (FileNotFoundError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Unexpected error during prediction: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
