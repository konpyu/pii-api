"""Unit tests for the API endpoints."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from pii_masking import Entity as DetectedEntity
from pii_masking import MaskingResult
from src.pii_masking.api.main import app


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def mock_pipeline():
    """Mock the masking pipeline."""
    with patch("src.pii_masking.api.main.pipeline") as mock:
        yield mock


class TestHealthCheck:
    """Test health check endpoint."""

    def test_health_check(self, client):
        """Test GET / returns healthy status."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "pii-masking-api"


class TestMaskEndpoint:
    """Test masking endpoint."""

    def test_mask_simple_text(self, client, mock_pipeline):
        """Test masking simple text without PII."""
        # Mock pipeline response
        mock_result = MaskingResult(
            masked_text="これは個人情報を含まないテキストです。",
            entities=[],
            risk_score=0.2,
            cached=False,
        )
        mock_pipeline.mask_text.return_value = mock_result

        # Make request
        response = client.post(
            "/mask", json={"text": "これは個人情報を含まないテキストです。"}
        )

        # Check response
        assert response.status_code == 200
        data = response.json()
        assert data["masked_text"] == "これは個人情報を含まないテキストです。"
        assert data["entities"] == []
        assert data["risk_score"] == 0.2
        assert data["cached"] is False

    def test_mask_with_phone_number(self, client, mock_pipeline):
        """Test masking text with phone number."""
        # Mock pipeline response
        mock_result = MaskingResult(
            masked_text="田中さんの電話番号は<MASK>です。",
            entities=[],
            risk_score=0.3,
            cached=False,
        )
        mock_pipeline.mask_text.return_value = mock_result

        # Make request
        response = client.post(
            "/mask", json={"text": "田中さんの電話番号は03-1234-5678です。"}
        )

        # Check response
        assert response.status_code == 200
        data = response.json()
        assert data["masked_text"] == "田中さんの電話番号は<MASK>です。"
        assert data["risk_score"] == 0.3

    def test_mask_with_entities(self, client, mock_pipeline):
        """Test masking text with detected entities."""
        # Mock pipeline response
        mock_result = MaskingResult(
            masked_text="<MASK>さんと<MASK>さんが会議をしました。",
            entities=[
                DetectedEntity(text="山田", label="PERSON", start=0, end=2),
                DetectedEntity(text="鈴木", label="PERSON", start=4, end=6),
            ],
            risk_score=0.9,
            cached=False,
        )
        mock_pipeline.mask_text.return_value = mock_result

        # Make request
        response = client.post(
            "/mask", json={"text": "山田さんと鈴木さんが会議をしました。"}
        )

        # Check response
        assert response.status_code == 200
        data = response.json()
        assert data["masked_text"] == "<MASK>さんと<MASK>さんが会議をしました。"
        assert len(data["entities"]) == 2
        assert data["entities"][0]["text"] == "山田"
        assert data["entities"][0]["label"] == "PERSON"
        assert data["entities"][1]["text"] == "鈴木"
        assert data["entities"][1]["label"] == "PERSON"
        assert data["risk_score"] == 0.9

    def test_cached_response(self, client, mock_pipeline):
        """Test cached response."""
        # Mock pipeline response
        mock_result = MaskingResult(
            masked_text="<MASK>です。",
            entities=[DetectedEntity(text="田中", label="PERSON", start=0, end=2)],
            risk_score=0.6,
            cached=True,
        )
        mock_pipeline.mask_text.return_value = mock_result

        # Make request
        response = client.post("/mask", json={"text": "田中です。"})

        # Check response
        assert response.status_code == 200
        data = response.json()
        assert data["cached"] is True

    def test_empty_text_error(self, client):
        """Test empty text returns 400 error."""
        response = client.post("/mask", json={"text": ""})
        assert response.status_code == 422  # Pydantic validation error

    def test_whitespace_only_text_error(self, client):
        """Test whitespace-only text returns 400 error."""
        response = client.post("/mask", json={"text": "   "})
        assert response.status_code == 400
        data = response.json()
        assert data["detail"] == "text is required"

    def test_text_too_long(self, client):
        """Test text exceeding 1024 bytes returns 422 error."""
        long_text = "あ" * 500  # Each Japanese character is 3 bytes in UTF-8
        response = client.post("/mask", json={"text": long_text})
        assert response.status_code == 422
        errors = response.json()["detail"]
        assert any("text exceeds 1024 bytes" in str(error) for error in errors)

    def test_missing_text_field(self, client):
        """Test missing text field returns 422 error."""
        response = client.post("/mask", json={})
        assert response.status_code == 422
        errors = response.json()["detail"]
        assert any(error["loc"] == ["body", "text"] for error in errors)

    def test_invalid_json(self, client):
        """Test invalid JSON returns 422 error."""
        response = client.post(
            "/mask", data="invalid json", headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 422

    def test_pipeline_not_initialized(self, client):
        """Test when pipeline is not initialized returns 500."""
        with patch("src.pii_masking.api.main.pipeline", None):
            response = client.post("/mask", json={"text": "test"})
            assert response.status_code == 500
            data = response.json()
            assert data["detail"] == "Internal server error"

    def test_pipeline_error(self, client, mock_pipeline):
        """Test pipeline error returns 500."""
        # Mock pipeline to raise exception
        mock_pipeline.mask_text.side_effect = Exception("Pipeline error")

        response = client.post("/mask", json={"text": "test"})
        assert response.status_code == 500
        data = response.json()
        assert data["detail"] == "Internal server error"
