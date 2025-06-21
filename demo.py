#!/usr/bin/env python3
"""Quick demo of PII masking pipeline."""

from pii_masking.core.pipeline import MaskingPipeline


def main():
    # パイプラインを初期化
    pipeline = MaskingPipeline()

    # テストケース
    test_cases = [
        "これは個人情報を含まないテキストです。",
        "田中さんの電話番号は03-1234-5678です。",
        "佐藤様のメールアドレスはsato@example.comです。",
        "東京都渋谷区の郵便番号は150-0002です。",
        "山田さんと鈴木さんが大阪で会議をしました。",
        "株式会社トヨタの田中様より、090-1234-5678にご連絡ください。",
        "マイナンバーは123456789012です。",
    ]

    print("=== PII Masking Pipeline Demo ===\n")

    for i, text in enumerate(test_cases, 1):
        print(f"Test {i}:")
        print(f"  Original: {text}")

        # マスキング実行
        result = pipeline.mask_text(text)

        print(f"  Masked:   {result.masked_text}")
        print(f"  Risk Score: {result.risk_score:.2f}")

        if result.entities:
            print("  Detected Entities:")
            for entity in result.entities:
                print(f"    - {entity.text} ({entity.label})")

        print(f"  Cached: {result.cached}")
        print()

    # キャッシュ動作確認
    print("=== Cache Test ===")
    test_text = "田中さんです。"

    print("First call:")
    result1 = pipeline.mask_text(test_text)
    print(f"  Cached: {result1.cached}")

    print("Second call (should be cached):")
    result2 = pipeline.mask_text(test_text)
    print(f"  Cached: {result2.cached}")
    print(f"  Same result: {result1.masked_text == result2.masked_text}")


if __name__ == "__main__":
    main()
