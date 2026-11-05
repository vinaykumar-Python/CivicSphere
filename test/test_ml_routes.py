import pytest
from unittest.mock import Mock

from app import ml_routes


@pytest.fixture
def citizen(client_for_user, test_database):
    db, data = test_database
    return client_for_user(data["citizen_one"])


class FakeMLModel:
    def predict(self, descriptions):
        return ["garbage"]

    def predict_proba(self, descriptions):
        return [[0.85, 0.15]]


def test_valid_complaint_prediction(citizen, monkeypatch):
    monkeypatch.setattr(ml_routes, "model", FakeMLModel())

    response = citizen.post(
        "/api/ml/predict",
        json={
            "description": "Garbage has not been collected near my apartment."
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["predicted_category"] == "garbage"
    assert data["confidence"] == pytest.approx(0.85)
    assert data["confidence_level"] == "high"
    assert data["model_type"] == "TF-IDF + Logistic Regression"


def test_short_description_rejected(citizen, monkeypatch):
    monkeypatch.setattr(ml_routes, "model", FakeMLModel())

    response = citizen.post(
        "/api/ml/predict",
        json={"description": "Road"},
    )

    assert response.status_code == 422


def test_whitespace_description_rejected(citizen):
    response = citizen.post(
        "/api/ml/predict",
        json={"description": "          "},
    )

    assert response.status_code == 422


def test_missing_description_rejected(citizen):
    response = citizen.post(
        "/api/ml/predict",
        json={},
    )

    assert response.status_code == 422


def test_prediction_returns_503_when_model_unavailable(
    citizen, monkeypatch
):
    monkeypatch.setattr(ml_routes, "model", None)

    response = citizen.post(
        "/api/ml/predict",
        json={
            "description": "Garbage is overflowing near my apartment."
        },
    )

    assert response.status_code == 503


def test_unsupported_category_rejected(citizen, monkeypatch):
    class UnsupportedModel:
        def predict(self, descriptions):
            return ["unsupported_category"]

    monkeypatch.setattr(ml_routes, "model", UnsupportedModel())

    response = citizen.post(
        "/api/ml/predict",
        json={
            "description": "Garbage is overflowing near my apartment."
        },
    )

    assert response.status_code == 500


def test_model_failure_returns_500(citizen, monkeypatch):
    class BrokenModel:
        def predict(self, descriptions):
            raise RuntimeError("Model prediction failed")

    monkeypatch.setattr(ml_routes, "model", BrokenModel())

    response = citizen.post(
        "/api/ml/predict",
        json={
            "description": "Garbage is overflowing near my apartment."
        },
    )

    assert response.status_code == 500


def test_invalid_confidence_returns_500(citizen, monkeypatch):
    class InvalidConfidenceModel:
        def predict(self, descriptions):
            return ["garbage"]

        def predict_proba(self, descriptions):
            return [float("nan"), 0.2]

    monkeypatch.setattr(
        ml_routes,
        "model",
        InvalidConfidenceModel(),
    )

    response = citizen.post(
        "/api/ml/predict",
        json={
            "description": "Garbage is overflowing near my apartment."
        },
    )

    assert response.status_code == 500


def test_ml_health_when_model_available(monkeypatch, client_for_user):
    monkeypatch.setattr(ml_routes, "model", FakeMLModel())

    client = client_for_user()

    response = client.get("/api/ml/health")

    assert response.status_code == 200
    assert response.json()["available"] is True
    assert response.json()["model_loaded"] is True


def test_ml_health_when_model_unavailable(monkeypatch, client_for_user):
    monkeypatch.setattr(ml_routes, "model", None)

    client = client_for_user()

    response = client.get("/api/ml/health")

    assert response.status_code == 200
    assert response.json()["available"] is False
    assert response.json()["model_loaded"] is False