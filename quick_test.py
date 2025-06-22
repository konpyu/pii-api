#!/usr/bin/env python3
"""最小限の動作確認コード"""

# プロジェクトルートで実行する場合
import sys

sys.path.insert(0, "src")

from pii_masking.core.pipeline import MaskingPipeline  # noqa: E402

print("=== Direct Pipeline Test ===")
# パイプライン作成
pipeline = MaskingPipeline()

# テキストをマスク
text = "田中さんの電話番号は03-1234-5678です。"
result = pipeline.mask_text(text)

print(f"元のテキスト: {text}")
print(f"マスク後:     {result.masked_text}")
print(f"リスクスコア: {result.risk_score:.2f}")
print(f"検出エンティティ: {[(e.text, e.label) for e in result.entities]}")

# API test (optional)
print("\n=== API Test (optional) ===")
print("To test the API:")
print("1. Run: uvicorn src.pii_masking.api.main:app --reload")
print("2. Then run: python test_api.py")
print("3. Or visit: http://localhost:8000/docs")
