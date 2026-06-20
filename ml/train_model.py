"""
train_model.py — Train a Random Forest disease classifier on the Kaggle dataset.

Standalone module (no Flask). Uses:
    ml/data/Training.csv  → training
    ml/data/Testing.csv   → evaluation

Target column: prognosis (auto-detected)
Features: all symptom columns (132 binary 0/1 columns)
"""

import os
import sys

import joblib
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
)
from sklearn.preprocessing import LabelEncoder

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TRAIN_PATH = os.path.join(BASE_DIR, "data", "Training.csv")
TEST_PATH = os.path.join(BASE_DIR, "data", "Testing.csv")
MODELS_DIR = os.path.join(BASE_DIR, "models")
MODEL_PATH = os.path.join(MODELS_DIR, "disease_model.pkl")
FEATURE_NAMES_PATH = os.path.join(MODELS_DIR, "feature_names.pkl")
LABEL_ENCODER_PATH = os.path.join(MODELS_DIR, "label_encoder.pkl")

# Column names that identify the disease label (checked in order)
TARGET_CANDIDATES = ("prognosis", "disease", "target", "label")

# Random Forest settings
RANDOM_STATE = 42
N_ESTIMATORS = 200  # more trees help on a larger multi-class dataset


def detect_target_column(df: pd.DataFrame) -> str:
    """
    Automatically find the target (disease) column.

    The Kaggle dataset uses 'prognosis'. We also accept common alternatives.
    If none match, the last non-symptom-looking column is used as a fallback.
    """
    usable_columns = [col for col in df.columns if not _is_junk_column(col)]

    for candidate in TARGET_CANDIDATES:
        for col in usable_columns:
            if str(col).strip().lower() == candidate:
                return col

    # Fallback: last column (typical layout in this dataset)
    return usable_columns[-1]


def _is_junk_column(column_name) -> bool:
    """True for empty pandas columns created by trailing commas in the CSV."""
    return str(column_name).startswith("Unnamed")


def get_feature_columns(df: pd.DataFrame, target_column: str) -> list:
    """
    All columns except the target and junk 'Unnamed' columns are symptoms.
    """
    return [
        col
        for col in df.columns
        if col != target_column and not _is_junk_column(col)
    ]


def load_kaggle_csv(csv_path: str) -> pd.DataFrame:
    """Load a CSV file or raise a clear error if it is missing."""
    if not os.path.isfile(csv_path):
        raise FileNotFoundError(
            f"Dataset not found: {csv_path}\n"
            "Place Training.csv and Testing.csv in ml/data/."
        )

    df = pd.read_csv(csv_path)
    if df.empty:
        raise ValueError(f"Dataset is empty: {csv_path}")

    return df


def preprocess_split(
    df: pd.DataFrame,
    target_column: str,
    feature_columns: list,
    source_name: str = "dataset",
) -> tuple:
    """
    Apply preprocessing to one dataframe (train or test).

    Steps:
        1. Drop junk 'Unnamed' columns from trailing commas in Training.csv
        2. Convert each symptom column to integer 0 or 1
        3. Strip whitespace from disease names in the prognosis column
        4. Drop rows with missing disease labels
    """
    df = df.copy()

    # Remove empty columns pandas creates from trailing commas
    junk_cols = [col for col in df.columns if _is_junk_column(col)]
    if junk_cols:
        df = df.drop(columns=junk_cols)

    missing_features = [col for col in feature_columns if col not in df.columns]
    if missing_features:
        raise ValueError(
            f"{source_name} is missing expected symptom columns: "
            f"{missing_features[:5]}{'...' if len(missing_features) > 5 else ''}"
        )

    # Binary symptom features: coerce to numeric, fill NaN with 0, clip to 0/1
    for col in feature_columns:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)
        df[col] = df[col].clip(0, 1)

    # Clean disease labels (e.g. "Fungal infection " → "Fungal infection")
    df[target_column] = df[target_column].astype(str).str.strip()
    df = df[df[target_column].notna() & (df[target_column] != "")]

    X = df[feature_columns]
    y = df[target_column]
    return X, y


def train_random_forest(X_train, y_train_encoded) -> RandomForestClassifier:
    """
    Train RandomForestClassifier.

    How Random Forest works (simple):
        - Builds many decision trees, each on a random subset of patients and symptoms.
        - Each tree asks yes/no questions like "itching == 1?" to split data.
        - At prediction time, every tree votes for a disease; the majority vote wins.
        - predict_proba() counts what fraction of trees voted for each disease.
    """
    model = RandomForestClassifier(
        n_estimators=N_ESTIMATORS,
        random_state=RANDOM_STATE,
        n_jobs=-1,
    )
    model.fit(X_train, y_train_encoded)
    return model


def evaluate_model(
    model: RandomForestClassifier,
    label_encoder: LabelEncoder,
    X_test,
    y_test_encoded,
) -> float:
    """Print accuracy, classification report, and confusion matrix."""
    y_pred = model.predict(X_test)
    accuracy = accuracy_score(y_test_encoded, y_pred)

    # Decode numeric labels back to disease names for readable reports
    y_test_names = label_encoder.inverse_transform(y_test_encoded)
    y_pred_names = label_encoder.inverse_transform(y_pred)

    print("\n" + "=" * 70)
    print("MODEL EVALUATION (Testing.csv)")
    print("=" * 70)
    print(f"\nAccuracy: {accuracy:.4f} ({accuracy * 100:.2f}%)\n")
    print("Classification Report:")
    print(classification_report(y_test_names, y_pred_names, zero_division=0))
    print("Confusion Matrix (rows = true disease, columns = predicted disease):")
    print(confusion_matrix(y_test_names, y_pred_names))
    print("=" * 70 + "\n")

    return accuracy


def save_artifacts(model, feature_names: list, label_encoder: LabelEncoder) -> None:
    """
    Save everything predict.py needs:
        disease_model.pkl   — trained RandomForestClassifier
        feature_names.pkl   — symptom column names in training order
        label_encoder.pkl   — maps encoded integers ↔ disease names
    """
    os.makedirs(MODELS_DIR, exist_ok=True)
    joblib.dump(model, MODEL_PATH)
    joblib.dump(feature_names, FEATURE_NAMES_PATH)
    joblib.dump(label_encoder, LABEL_ENCODER_PATH)

    print(f"Saved model to:         {MODEL_PATH}")
    print(f"Saved feature names to: {FEATURE_NAMES_PATH}")
    print(f"Saved label encoder to: {LABEL_ENCODER_PATH}")


def main() -> int:
    try:
        print("Loading Kaggle dataset...")
        train_df = load_kaggle_csv(TRAIN_PATH)
        test_df = load_kaggle_csv(TEST_PATH)

        target_column = detect_target_column(train_df)
        feature_columns = get_feature_columns(train_df, target_column)

        if detect_target_column(test_df) != target_column:
            test_target = detect_target_column(test_df)
            if test_target != target_column:
                print(
                    f"Warning: train target '{target_column}', test target '{test_target}'. "
                    f"Using '{target_column}' from training file."
                )

        print(f"Target column:    {target_column}")
        print(f"Symptom features: {len(feature_columns)}")
        print(f"Training rows:    {len(train_df)}")
        print(f"Testing rows:     {len(test_df)}")

        X_train, y_train = preprocess_split(
            train_df, target_column, feature_columns, source_name="Training.csv"
        )
        X_test, y_test = preprocess_split(
            test_df, target_column, feature_columns, source_name="Testing.csv"
        )

        num_diseases = y_train.nunique()
        print(f"Diseases (classes): {num_diseases}")

        # LabelEncoder converts disease names → 0, 1, 2, ... for the classifier
        label_encoder = LabelEncoder()
        y_train_encoded = label_encoder.fit_transform(y_train)
        y_test_encoded = label_encoder.transform(y_test)

        print(f"\nTraining Random Forest on {len(X_train)} samples...")
        model = train_random_forest(X_train, y_train_encoded)

        evaluate_model(model, label_encoder, X_test, y_test_encoded)
        save_artifacts(model, feature_columns, label_encoder)

        print("Training completed successfully.")
        return 0

    except (FileNotFoundError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Unexpected error during training: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
