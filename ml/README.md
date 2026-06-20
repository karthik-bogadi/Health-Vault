# HealthVault — Disease Prediction ML Module

Standalone machine learning pipeline using the **Kaggle Disease Prediction dataset**. Not connected to Flask or `app.py`.

## Folder structure

```
ml/
├── train_model.py          # Train on Training.csv, evaluate on Testing.csv
├── predict.py              # Predict top 3 diseases from symptom names
├── models/
│   ├── disease_model.pkl   # Trained RandomForestClassifier
│   ├── feature_names.pkl   # 132 symptom column names (order matters)
│   └── label_encoder.pkl   # Maps encoded labels ↔ disease names
├── data/
│   ├── Training.csv        # Kaggle training set (~4920 rows)
│   └── Testing.csv         # Kaggle test set (~42 rows)
└── README.md
```

## Dataset format (Kaggle)

| Part | Description |
|------|-------------|
| Symptom columns | 132 columns, binary `0` or `1` |
| Target column | `prognosis` (disease name, e.g. `Fungal infection`) |
| Training | `ml/data/Training.csv` |
| Testing | `ml/data/Testing.csv` |

Example header:

```csv
itching,skin_rash,...,prognosis
1,1,0,...,Fungal infection
```

## How the dataset is processed

1. **Load** `Training.csv` and `Testing.csv` with pandas.
2. **Auto-detect** target column (`prognosis`).
3. **Drop** junk `Unnamed` columns from trailing commas in the training file.
4. **Features** = all columns except `prognosis` (132 symptoms).
5. **Preprocessing** on symptom columns:
   - Convert to numeric
   - Fill missing values with `0`
   - Clip to `0` or `1`
6. **Clean** disease labels (strip whitespace).
7. **Encode** disease names with `LabelEncoder` for training.
8. **Train** Random Forest on all training rows.
9. **Evaluate** on the separate `Testing.csv` (not a random split).

## How symptom names become features

At prediction time you pass names like `itching`, `skin_rash`, or `high fever`.

`predict.py`:

1. Normalizes names (lowercase, spaces → underscores).
2. Builds a vector of length 132: `1` if symptom present, else `0`.
3. Passes that row to the model in the same column order saved in `feature_names.pkl`.

## How confidence scores work

`RandomForestClassifier.predict_proba()` returns the **fraction of trees** in the forest that voted for each disease.

- `0.65` → **65% confidence**
- Top 3 diseases = three highest probabilities

## Random Forest (simple explanation)

- Builds many decision trees on random subsets of data and symptoms.
- Each tree learns simple rules (`if itching == 1 and skin_rash == 1 → ...`).
- All trees vote; the class with the most votes wins.
- Probabilities = share of votes per disease.

## Terminal commands

### Install dependencies

```bash
pip install pandas scikit-learn joblib
```

### Train the model

```bash
cd ml
python train_model.py
```

Prints:

- Number of symptoms and diseases
- Accuracy on `Testing.csv`
- Classification report
- Confusion matrix

Saves `models/disease_model.pkl`, `feature_names.pkl`, `label_encoder.pkl`.

### Test prediction

```bash
python predict.py itching skin_rash
python predict.py --symptoms itching,skin_rash,continuous_sneezing
python predict.py cough high_fever chest_pain --top 5
```

## Symptom name tips

Use CSV column names (underscores):

- `skin_rash`, `high_fever`, `continuous_sneezing`
- Spaces also work: `skin rash` → `skin_rash`

Unknown symptoms are ignored with a warning.

## Preprocessing notes

| Step | Why |
|------|-----|
| Drop `Unnamed` columns | Training.csv has a trailing comma creating an empty column |
| Binary clip 0/1 | Ensures invalid values do not break the model |
| `LabelEncoder` | Converts 41 disease names to integers for sklearn |
| Duplicate `fluid_overload` | Pandas names the second column `fluid_overload.1` automatically |

## Next steps (not implemented)

- Integrate with HealthVault Flask routes
- Connect ML predictions to patient report selection
