"""
Flask integration layer for disease prediction.

Wraps ml/predict.py so the web app can load symptoms and run predictions
without duplicating ML logic or retraining the model.
"""

from typing import List, Tuple

from ml.predict import (
    find_unknown_symptoms,
    load_artifacts,
    normalize_symptom_name,
    predict_top_diseases,
)


class ModelNotAvailableError(FileNotFoundError):
    """Raised when one or more model artifact files are missing."""


class InvalidSymptomsError(ValueError):
    """Raised when submitted symptoms are empty or not in the training dataset."""


def format_symptom_label(column_name: str) -> str:
    """Turn CSV column names into readable labels (skin_rash -> Skin Rash)."""
    return column_name.replace("_", " ").replace(".", " ").strip().title()


def get_available_symptoms() -> List[dict]:
    """
    Load symptom names from feature_names.pkl for the checkbox UI.

    Returns a list of dicts: {"value": "skin_rash", "label": "Skin Rash"}
    """
    try:
        _, feature_names, _ = load_artifacts()
    except FileNotFoundError as exc:
        raise ModelNotAvailableError(str(exc)) from exc

    if not feature_names:
        raise ModelNotAvailableError("feature_names.pkl is empty. Retrain the model.")

    return [
        {"value": name, "label": format_symptom_label(name)}
        for name in feature_names
    ]


def validate_selected_symptoms(selected: List[str], feature_names: List[str]) -> List[str]:
    """
    Keep only symptoms that exist in the trained feature list.
    Raises InvalidSymptomsError if nothing valid remains.
    """
    if not selected:
        raise InvalidSymptomsError("Please select at least one symptom.")

    allowed = {normalize_symptom_name(name): name for name in feature_names}
    validated = []
    invalid = []

    for raw in selected:
        cleaned = raw.strip()
        if not cleaned:
            continue
        key = normalize_symptom_name(cleaned)
        if key in allowed:
            canonical = allowed[key]
            if canonical not in validated:
                validated.append(canonical)
        else:
            invalid.append(cleaned)

    if invalid and not validated:
        raise InvalidSymptomsError(
            f"Invalid symptoms: {', '.join(invalid)}. "
            "Please choose symptoms from the list."
        )

    if not validated:
        raise InvalidSymptomsError("Please select at least one symptom.")

    return validated


def predict_diseases(selected_symptoms: List[str], top_k: int = 3) -> Tuple[List[Tuple[str, float]], List[str]]:
    """
    Run disease prediction using the saved model (no retraining).

    Returns:
        (predictions, warnings)
        predictions: [(disease_name, confidence_percent), ...]
        warnings: unknown symptom names that were ignored (should not happen with checkboxes)
    """
    try:
        _, feature_names, _ = load_artifacts()
    except FileNotFoundError as exc:
        raise ModelNotAvailableError(str(exc)) from exc

    validated = validate_selected_symptoms(selected_symptoms, feature_names)
    warnings = find_unknown_symptoms(selected_symptoms, feature_names)
    predictions = predict_top_diseases(validated, top_k=top_k)
    return predictions, warnings
