from pathlib import Path
import json

import joblib
import matplotlib.pyplot as plt
import pandas as pd

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    ConfusionMatrixDisplay,
    f1_score,
)
from sklearn.model_selection import (
    train_test_split,
    StratifiedKFold,
    cross_val_score,
)
from sklearn.pipeline import Pipeline


# --------------------------------------------------
# 1. Paths
# --------------------------------------------------

ML_DIR = Path(__file__).resolve().parent
DATA_PATH = ML_DIR / "data" / "complaint_training.csv"
MODEL_DIR = ML_DIR / "models"

MODEL_PATH = MODEL_DIR / "complaint_classifier.joblib"
REPORT_PATH = MODEL_DIR / "evaluation_report.json"
MATRIX_PATH = MODEL_DIR / "confusion_matrix.png"

MODEL_DIR.mkdir(parents=True, exist_ok=True)


# --------------------------------------------------
# 2. Load and validate dataset
# --------------------------------------------------

if not DATA_PATH.exists():
    raise FileNotFoundError(
        f"Training dataset not found: {DATA_PATH}"
    )

data = pd.read_csv(DATA_PATH)

required_columns = {"description", "category"}

if not required_columns.issubset(data.columns):
    raise ValueError(
        "Dataset must contain description and category columns."
    )

data = data.dropna(
    subset=["description", "category"]
).copy()

data["description"] = (
    data["description"].astype(str).str.strip()
)

data["category"] = (
    data["category"].astype(str).str.strip().str.lower()
)

data = data[
    (data["description"] != "")
    & (data["category"] != "")
].copy()

data = data.reset_index(drop=True)

if data["category"].nunique() < 2:
    raise ValueError(
        "At least two complaint categories are required."
    )

category_counts = data["category"].value_counts()

if category_counts.min() < 5:
    raise ValueError(
        "Every category needs at least five examples "
        "for stratified 5-fold cross-validation."
    )

print("\n========== DATASET SUMMARY ==========")
print(f"Total examples: {len(data)}")
print(f"Categories: {data['category'].nunique()}")
print(category_counts.to_string())


# --------------------------------------------------
# 3. Split into training and held-out test sets
# --------------------------------------------------

X_train, X_test, y_train, y_test = train_test_split(
    data["description"],
    data["category"],
    test_size=0.25,
    random_state=42,
    stratify=data["category"],
)


# --------------------------------------------------
# 4. Build classification pipeline
# --------------------------------------------------

model = Pipeline(
    [
        (
            "tfidf",
            TfidfVectorizer(
                lowercase=True,
                ngram_range=(1, 2),
                stop_words="english",
            ),
        ),
        (
            "classifier",
            LogisticRegression(
                max_iter=2000,
                class_weight="balanced",
                random_state=42,
            ),
        ),
    ]
)


# --------------------------------------------------
# 5. Cross-validation on the training partition only
# --------------------------------------------------

cv = StratifiedKFold(
    n_splits=5,
    shuffle=True,
    random_state=42,
)

cv_scores = cross_val_score(
    model,
    X_train,
    y_train,
    cv=cv,
    scoring="accuracy",
)

cv_f1_scores = cross_val_score(
    model,
    X_train,
    y_train,
    cv=cv,
    scoring="f1_macro",
)

print("\n========== TRAINING-SET CROSS-VALIDATION ==========")
print("Accuracy per fold:", cv_scores.round(3))
print(f"Mean CV accuracy: {cv_scores.mean():.2%}")
print(f"CV accuracy standard deviation: {cv_scores.std():.2%}")
print("Macro F1 per fold:", cv_f1_scores.round(3))
print(f"Mean CV macro F1: {cv_f1_scores.mean():.2%}")


# --------------------------------------------------
# 6. Train and evaluate on held-out test data
# --------------------------------------------------

model.fit(X_train, y_train)

predictions = model.predict(X_test)

labels = sorted(data["category"].unique())

test_accuracy = accuracy_score(y_test, predictions)

macro_f1 = f1_score(
    y_test,
    predictions,
    labels=labels,
    average="macro",
    zero_division=0,
)

report_data = classification_report(
    y_test,
    predictions,
    labels=labels,
    output_dict=True,
    zero_division=0,
)

print("\n========== HELD-OUT TEST RESULTS ==========")
print(f"Training examples: {len(X_train)}")
print(f"Test examples: {len(X_test)}")
print(f"Test accuracy: {test_accuracy:.2%}")
print(f"Test macro F1-score: {macro_f1:.2%}")

print("\nClassification report:")
print(
    classification_report(
        y_test,
        predictions,
        labels=labels,
        zero_division=0,
    )
)


# --------------------------------------------------
# 7. Save confusion matrix
# --------------------------------------------------

matrix = confusion_matrix(
    y_test,
    predictions,
    labels=labels,
)

fig, ax = plt.subplots(figsize=(10, 7))

ConfusionMatrixDisplay(
    confusion_matrix=matrix,
    display_labels=labels,
).plot(
    ax=ax,
    xticks_rotation=45,
    values_format="d",
    cmap="Blues",
    colorbar=False,
)

ax.set_title(
    "CivicCare AI - Complaint Classification"
)

fig.tight_layout()

fig.savefig(
    MATRIX_PATH,
    dpi=150,
    bbox_inches="tight",
    facecolor="white",
)

plt.close(fig)

print(f"\nConfusion matrix saved: {MATRIX_PATH}")


# --------------------------------------------------
# 8. Save evaluation report
# --------------------------------------------------

evaluation_report = {
    "model": "TF-IDF + Logistic Regression",
    "dataset_size": int(len(data)),
    "training_samples": int(len(X_train)),
    "testing_samples": int(len(X_test)),
    "categories": labels,
    "test_accuracy": float(test_accuracy),
    "test_macro_f1": float(macro_f1),
    "cross_validation_accuracy_mean": float(
        cv_scores.mean()
    ),
    "cross_validation_accuracy_std": float(
        cv_scores.std()
    ),
    "cross_validation_macro_f1_mean": float(
        cv_f1_scores.mean()
    ),
    "classification_report": report_data,
    "evaluation_note": (
        "Metrics are based on a small complaint dataset. "
        "Validate using additional independent, representative "
        "complaints before production use."
    ),
}

with open(
    REPORT_PATH,
    "w",
    encoding="utf-8",
) as file:
    json.dump(
        evaluation_report,
        file,
        indent=4,
    )

print(f"Evaluation report saved: {REPORT_PATH}")


# --------------------------------------------------
# 9. Display misclassified test examples
# --------------------------------------------------

print("\n========== MISCLASSIFIED COMPLAINTS ==========")

error_count = 0

for description, actual, predicted in zip(
    X_test,
    y_test,
    predictions,
):
    if actual != predicted:
        error_count += 1

        print(f"\nComplaint: {description}")
        print(f"Actual category: {actual}")
        print(f"Predicted category: {predicted}")

print(
    f"\nMisclassified examples: "
    f"{error_count}/{len(y_test)}"
)


# --------------------------------------------------
# 10. Save trained model after evaluation artifacts
# --------------------------------------------------

joblib.dump(model, MODEL_PATH)

print(f"\nModel saved: {MODEL_PATH}")
print("Training and evaluation completed.")
