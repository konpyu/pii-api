#!/usr/bin/env python3
"""Simple test script for the PII masking API."""

import requests


def test_api():
    """Test the API with various inputs."""
    base_url = "http://localhost:8000"

    # Test cases from demo.py
    test_cases = [
        "これは個人情報を含まないテキストです。",
        "田中さんの電話番号は03-1234-5678です。",
        "佐藤様のメールアドレスはsato@example.comです。",
        "東京都渋谷区の郵便番号は150-0002です。",
        "山田さんと鈴木さんが大阪で会議をしました。",
        "株式会社トヨタの田中様より、090-1234-5678にご連絡ください。",
        "マイナンバーは123456789012です。",
    ]

    print("Testing PII Masking API...")
    print(f"URL: {base_url}/mask\n")

    # Test health check
    try:
        response = requests.get(f"{base_url}/")
        print(f"Health check: {response.json()}\n")
    except Exception as e:
        print(f"Health check failed: {e}\n")

    # Test masking endpoint
    for i, text in enumerate(test_cases, 1):
        print(f"Test {i}:")
        print(f"  Input: {text}")

        try:
            response = requests.post(
                f"{base_url}/mask",
                json={"text": text},
                headers={"Content-Type": "application/json"},
            )

            if response.status_code == 200:
                data = response.json()
                print(f"  Masked: {data['masked_text']}")
                print(f"  Risk Score: {data['risk_score']}")
                print(f"  Cached: {data['cached']}")
                if data["entities"]:
                    print("  Entities:")
                    for entity in data["entities"]:
                        print(f"    - {entity['text']} ({entity['label']})")
            else:
                print(f"  Error: {response.status_code} - {response.text}")

        except Exception as e:
            print(f"  Failed: {e}")

        print()

    # Test error cases
    print("Testing error cases:")

    # Empty text
    print("1. Empty text:")
    response = requests.post(f"{base_url}/mask", json={"text": ""})
    print(f"   Status: {response.status_code}")
    print(f"   Response: {response.json()}\n")

    # Invalid JSON
    print("2. Invalid JSON:")
    response = requests.post(
        f"{base_url}/mask", data="invalid", headers={"Content-Type": "application/json"}
    )
    print(f"   Status: {response.status_code}")
    print(f"   Response: {response.json()}\n")

    # Missing field
    print("3. Missing field:")
    response = requests.post(f"{base_url}/mask", json={})
    print(f"   Status: {response.status_code}")
    print(f"   Response: {response.json()}\n")


if __name__ == "__main__":
    test_api()
