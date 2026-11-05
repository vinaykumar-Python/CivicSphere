from pathlib import Path
import json
import logging
import math

import joblib
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, field_validator

from app.dependencies import get_current_user
from app.models import User
from app.category_routes import get_complaint_categories

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ml", tags=["Machine Learning"])

PROJECT_DIR = Path(__file__).resolve().parent.parent

MODEL_PATH = PROJECT_DIR / "ml" / "models" / "complaint_classifier.joblib"
EVALUATION_PATH = PROJECT_DIR / "ml" / "models" / "evaluation_report.json"
CONFUSION_MATRIX_PATH = PROJECT_DIR / "ml" / "models" / "confusion_matrix.png"

model = None

if MODEL_PATH.exists():
    try:
        model = joblib.load(MODEL_PATH)
        logger.info("Complaint classification model loaded.")
    except Exception:
        logger.exception("Could not load complaint classification model.")
else:
    logger.warning("Complaint classification model file not found.")


class ComplaintPredictionRequest(BaseModel):
    description: str = Field(
        ...,
        min_length=10,
        max_length=3000,
        description="Description of the civic complaint",
    )

    @field_validator("description")
    @classmethod
    def validate_description(cls, value):
        value = value.strip()

        if len(value) < 10:
            raise ValueError(
                "Please provide a complaint description of at least 10 characters."
            )

        return value


class ComplaintPredictionResponse(BaseModel):
    description: str
    predicted_category: str
    confidence: float | None
    confidence_level: str
    recommendation: str
    model_type: str
    warning: str


@router.get("/health")
def ml_health():
    return {
        "available": model is not None,
        "model_loaded": model is not None,
    }


@router.post("/predict", response_model=ComplaintPredictionResponse)
def predict_complaint(
    request: ComplaintPredictionRequest,
    current_user: User = Depends(get_current_user),
):
    if model is None:
        raise HTTPException(
            status_code=503,
            detail="Complaint classification model is currently unavailable.",
        )

    description = request.description

    try:
        predicted_category = str(model.predict([description])[0]).strip()

        if not predicted_category:
            raise ValueError("Model returned an empty category.")

        # Validate that the model output is a supported CivicCare category.
        category_data = get_complaint_categories()

        supported_categories = {
            str(item["value"]).strip().lower()
            for item in category_data["categories"]
        }

        if predicted_category.lower() not in supported_categories:
            logger.error(
                "Model returned unsupported category: %s",
                predicted_category,
            )
            raise HTTPException(
                status_code=500,
                detail="The model returned an unsupported complaint category.",
            )

        confidence = None

        if hasattr(model, "predict_proba"):
            probabilities = model.predict_proba([description])[0]

            confidence = float(max(probabilities))

            if not math.isfinite(confidence) or not 0 <= confidence <= 1:
                raise ValueError("Model returned invalid confidence.")

        if confidence is None:
            confidence_level = "unavailable"
            recommendation = (
                "Review the suggested category manually before submitting."
            )
        elif confidence >= 0.75:
            confidence_level = "high"
            recommendation = (
                "Review the suggested category and confirm before submitting."
            )
        elif confidence >= 0.50:
            confidence_level = "medium"
            recommendation = (
                "Check the suggested category carefully. "
                "Choose another category if it better describes the issue."
            )
        else:
            confidence_level = "low"
            recommendation = (
                "The AI is uncertain. Please select the correct category manually."
            )

        return ComplaintPredictionResponse(
            description=description,
            predicted_category=predicted_category,
            confidence=confidence,
            confidence_level=confidence_level,
            recommendation=recommendation,
            model_type="TF-IDF + Logistic Regression",
            warning=(
                "Experimental model trained on synthetic complaint examples. "
                "Confidence is not a guarantee of correctness. "
                "Verify the category before submitting or routing a complaint."
            ),
        )

    except HTTPException:
        raise
    except Exception:
        logger.exception("Complaint classification failed.")
        raise HTTPException(
            status_code=500,
            detail="The complaint could not be classified.",
        )


@router.get("/evaluation")
def get_ml_evaluation():
    if not EVALUATION_PATH.exists():
        return {
            "available": False,
            "message": "Evaluation report not found. Train the model first.",
        }

    try:
        with open(EVALUATION_PATH, "r", encoding="utf-8") as file:
            report = json.load(file)

        return {
            "available": True,
            "evaluation": report,
        }

    except (OSError, json.JSONDecodeError):
        logger.exception("Could not read ML evaluation report.")
        raise HTTPException(
            status_code=500,
            detail="The model evaluation report could not be read.",
        )


@router.get("/confusion-matrix")
def get_confusion_matrix():
    if not CONFUSION_MATRIX_PATH.exists():
        raise HTTPException(
            status_code=404,
            detail="Confusion matrix image not found. Train the model first.",
        )

    return FileResponse(
        path=str(CONFUSION_MATRIX_PATH),
        media_type="image/png",
        filename="confusion_matrix.png",
    )