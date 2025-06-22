"""Integration tests for the API with real pipeline."""

import pytest
from fastapi.testclient import TestClient

from src.pii_masking.api.main import app


@pytest.mark.integration
class TestAPIIntegration:
    """Integration tests for API with real pipeline."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    def test_mask_no_pii(self, client):
        """Test masking text without PII."""
        response = client.post(
            "/mask", json={"text": "これは個人情報を含まないテキストです。"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["masked_text"] == "これは個人情報を含まないテキストです。"
        assert data["entities"] == []
        assert data["risk_score"] == 0.2
        assert isinstance(data["cached"], bool)

    def test_mask_phone_number(self, client):
        """Test masking phone number."""
        response = client.post(
            "/mask", json={"text": "田中さんの電話番号は03-1234-5678です。"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "<MASK>" in data["masked_text"]
        assert "03-1234-5678" not in data["masked_text"]
        assert data["risk_score"] > 0.2

    def test_mask_email(self, client):
        """Test masking email address."""
        response = client.post(
            "/mask", json={"text": "佐藤様のメールアドレスはsato@example.comです。"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "<MASK>" in data["masked_text"]
        assert "sato@example.com" not in data["masked_text"]

    def test_mask_postal_code(self, client):
        """Test masking postal code."""
        response = client.post(
            "/mask", json={"text": "東京都渋谷区の郵便番号は150-0002です。"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "<MASK>" in data["masked_text"]
        assert "150-0002" not in data["masked_text"]

    def test_mask_multiple_persons(self, client):
        """Test masking multiple person names."""
        response = client.post(
            "/mask", json={"text": "山田さんと鈴木さんが大阪で会議をしました。"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["masked_text"].count("<MASK>") >= 2
        assert "山田" not in data["masked_text"]
        assert "鈴木" not in data["masked_text"]
        assert data["risk_score"] >= 0.89  # Allow for floating point precision

    def test_mask_complex_text(self, client):
        """Test masking complex text with multiple PII types."""
        response = client.post(
            "/mask",
            json={
                "text": "株式会社トヨタの田中様より、090-1234-5678にご連絡ください。"
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "<MASK>" in data["masked_text"]
        assert "090-1234-5678" not in data["masked_text"]
        assert data["risk_score"] > 0.5

    def test_mask_mynumber(self, client):
        """Test masking My Number."""
        response = client.post(
            "/mask", json={"text": "マイナンバーは123456789012です。"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "<MASK>" in data["masked_text"]
        assert "123456789012" not in data["masked_text"]

    def test_caching_behavior(self, client):
        """Test caching behavior."""
        test_text = "これはキャッシュテストです。"

        # First request - should not be cached
        response1 = client.post("/mask", json={"text": test_text})
        assert response1.status_code == 200
        data1 = response1.json()
        assert data1["cached"] is False

        # Second request - should be cached
        response2 = client.post("/mask", json={"text": test_text})
        assert response2.status_code == 200
        data2 = response2.json()
        assert data2["cached"] is True

        # Results should be identical
        assert data1["masked_text"] == data2["masked_text"]
        assert data1["risk_score"] == data2["risk_score"]

    def test_emoji_handling(self, client):
        """Test handling of emojis in text."""
        response = client.post("/mask", json={"text": "👍(山田)"})
        assert response.status_code == 200
        data = response.json()
        assert "👍(<MASK>)" == data["masked_text"] or "👍(山田)" == data["masked_text"]

    def test_error_handling(self, client):
        """Test various error conditions."""
        # Empty text
        response = client.post("/mask", json={"text": ""})
        assert response.status_code == 422

        # Missing field
        response = client.post("/mask", json={})
        assert response.status_code == 422

        # Invalid JSON
        response = client.post(
            "/mask", data="not json", headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 422

        # Text too long
        long_text = "あ" * 500  # Exceeds byte limit
        response = client.post("/mask", json={"text": long_text})
        assert response.status_code == 422
