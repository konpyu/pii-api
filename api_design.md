# PII マスキング基盤 — 統合設計書

## 1. 目的
本書は、日本語テキストを対象とする PII（個人識別情報）マスキング API の軽量 CPU スタックに関する統合設計書である。インフラ、API 仕様、マスキングロジック、テスト要件を網羅し、開発者が本ドキュメントのみを authoritative source として参照できることを目指す。

---
## 2. スコープ
| 項目 | 内容 |
|------|------|
| 対象処理 | テキスト入力（~1 KB/件）の同期マスキング、非同期リスク集計（k‑匿名性 等） |
| 非対象 | 画像 OCR / EXIF 処理、GPU 推論、オンプレ展開 |
| ユーザー | 社内システムおよび社外 B2B API 利用者 |

---
## 3. アーキテクチャ概要
```
Client → HTTPS → Cloud Run (FastAPI)
   ├─ Regex Layer (re2 / Hyperscan)
   ├─ Tokenizer (SudachiPy)
   ├─ NER Inference (ONNX INT8 DistilBERT‑JP)
   ├─ Redis Cache (optional hit)
   └─ Pub/Sub  → DuckDB Batch Job (Risk Aggregation)
                      └─ Cloud Storage / BigQuery (ログ & メタ)
```

---
## 4. API エンドポイント仕様 (`/mask`)

- **Method**: `POST`
- **Content-Type**: `application/json`

### 4.1 リクエストボディ

```json
{
  "text": "string"
}
```

| フィールド | 型 | 説明 | 必須 | 制約 |
|---|---|---|---|---|
| `text` | string | マスキング対象の日本語テキスト | ✅ | 1 <= `len(text)` <= 1024 bytes |

### 4.2 レスポンスボディ (正常時: `200 OK`)

```json
{
  "masked_text": "string",
  "entities": [
    {
      "text": "string",
      "label": "string"
    }
  ],
  "risk_score": "float",
  "cached": "boolean"
}
```

| フィールド | 型 | 説明 |
|---|---|---|
| `masked_text` | string | PII を `<MASK>` トークンで置換したテキスト |
| `entities` | array | 検出された PII エンティティのリスト（正規表現によるものは除く） |
| `risk_score` | float | テキストの識別リスクを示すスコア (0.0-1.0) |
| `cached` | boolean | レスポンスがキャッシュから返されたか否か |

### 4.3 エラーレスポンス

| ステータスコード | エラータイプ | 条件 | レスポンス例 |
|---|---|---|---|
| `400 Bad Request` | `ValidationError` | `text` が空、長すぎる、または `null` | `{"detail": "text is required"}` |
| `422 Unprocessable Entity` | `Unprocessable Entity` | リクエストボディが不正な JSON | `{"detail": [...]}` (FastAPI 標準) |
| `500 Internal Server Error` | `ServerError` | NER モデルロード失敗など、サーバ内部の問題 | `{"detail": "Internal server error"}` |

---
## 5. マスキング処理 & リスク評価ロジック

### 5.1 処理パイプライン
1. **キャッシュ確認**: SHA-256(text) をキーに Redis を検索。ヒットすれば即時返却。
2. **正規表現マスキング**: `REGEX_PATTERNS` に定義されたパターン（電話番号、郵便番号等）を先に `<MASK>` 置換する。
3. **NER によるエンティティ抽出**: `SudachiPy` で形態素解析後、ONNX Runtime で `line-distilbert-base-japanese` を用いて `PERSON` 等の固有表現を抽出する。
4. **NER 結果マスキング**: 抽出されたエンティティを `<MASK>` 置換する。
5. **リスクスコア計算**: `compute_risk_score` 関数により、検出エンティティに基づいてスコアを算出。
6. **キャッシュ保存**: 生成したレスポンスを Redis に TTL 24h で保存。

### 5.2 正規表現パターン
PoC 実装 (`concept-implementation.py`) をベースとし、以下のパターンを re2 で実装する。

| PII タイプ | 正規表現 | 例 |
|---|---|---|
| 電話番号 | `\b0\d{1,3}-\d{1,4}-\d{4}\b` | `03-1234-5678` |
| 郵便番号 | `\b\d{3}-\d{4}\b` | `150-0002` |
| マイナンバー (数字のみ) | `\b\d{12}\b` | `123456789012` |

### 5.3 リスクスコア計算ロジック
PoC の仮実装を拡張し、以下のルールでスコアを決定する。

- **ベーススコア**: 0.2 (PII なし)
- **加点**:
  - `PERSON` エンティティ 1 件につき: +0.4
  - `PERSON` エンティティ 2 件以上: +0.7 (上限)
  - 正規表現マッチ 1 種につき: +0.1
- **最大値**: スコアは 1.0 を超えない。

```python
# concept
def compute_risk_score(entities, regex_matches):
    score = 0.2
    person_count = len([e for e in entities if e["label"] == "PERSON"])
    if person_count == 1:
        score += 0.4
    elif person_count >= 2:
        score += 0.7

    score += len(regex_matches) * 0.1
    return min(1.0, score)
```

---
## 6. コンポーネント要件
| # | コンポーネント | 技術/サービス | サイズ & 設定 | 可用性 | 補足 |
|---|--------------|---------------|---------------|--------|------|
| 1 | **API 層** | Cloud Run (container) | `e2-standard-4` ×2, auto-scale 0–6 | 99.5 % | FastAPI + Uvicorn、10 MiB メモリバッファ |
| 2 | **Regex レイヤ** | re2 ライブラリ | 同上 | – | Hyperscan 置換可 |
| 3 | **Tokenizer** | SudachiPy (core dict) | 同上 | – | MeCab 互換辞書不要 |
| 4 | **NER 推論** | ONNX Runtime INT8、モデル: `line-distilbert-base-japanese` | 同上 | – | 25–40 ms/1k 字 (P95) |
| 5 | **キャッシュ** | Cloud Memorystore (Redis) | 1 GB、max‑memory‑policy allkeys‑lru | 99.9 % | TTL 24 h、推論結果キー=SHA‑256(input) |
| 6 | **メッセージキュー** | Pub/Sub Topic + Subscription | 7 日保持, Ack deadline 60 s | 99.9 % | ストリームバッファ兼バックプレッシャ |
| 7 | **リスク集計** | Cloud Run Job → DuckDB | `e2-standard-4`, 1 job/min | – | parquet append; k=5, l=2, rarity スコア計算 |
| 8 | **ストレージ** | Cloud Storage (Coldline) | 30 GB 想定 | 99.99 % | 生ログ + マスク済みデータ保管 |
| 9 | **監視** | Cloud Monitoring & Logging | – | – | SLA/ErrorRate/GCS バケットサイズ等 |

---
## 7. テストケース & 受入基準
`test_prd.md` から主要なテストケースを抜粋。

### 7.1 機能テストケース (API レベル)
| ID | テスト意図 | text 例 | 期待 masked_text | 期待 entities | 期待 risk* |
|----|------------|---------|------------------|---------------|------------|
| TC01 | 電話番号 | 至急 03-1234-5678 まで！ | 至急 <MASK> まで！ | [] | 0.3 |
| TC03 | 人名 | 佐藤に資料投げました | <MASK>に資料投げました | 1×PERSON | 0.6 |
| TC04 | 人名＋電話 | 山田です。携帯は 090-1111-2222 | <MASK>です。携帯は <MASK> | 1×PERSON | 0.7 |
| TC05 | 2 人名 | 田中と鈴木で確認済み | <MASK>と<MASK>で確認済み | 2×PERSON | 0.9 |
| TC09 | 姓＋企業名 | 佐藤工業の佐藤が来社 | 佐藤工業の<MASK>が来社 | 1×PERSON | 0.6 |
| TC17 | 絵文字内人名 | 👍(山田) | 👍(<MASK>) | 1×PERSON | 0.6 |

> *risk スコアは上記ロジックに基づく概算値。

### 7.2 受入基準
| 区分 | 指標 | 目標値 |
|---|---|---|
| **機能** | 上記テストケースのマスク結果・リスクスコアが期待どおり | 100 % 合格 |
| **性能** | 平常 80 RPS / ピーク 200 RPS における `P95` | ≤ 120 ms |
| **可用性** | レスポンスエラー率 | ≤ 0.1 % |
| **キャッシュ** | 同一入力 2 回目以降の `cached` フラグ | `True` & レイテンシ半減 |

---
## 8. 性能要件
| 指標 | 目標値 | 備考 |
|------|--------|------|
| 同時リクエスト | 80 RPS (平常), 200 RPS (ピーク5 min) | Auto‑scale 対応 |
| レイテンシ (P95) | ≤120 ms / 1 KB 入力 | キャッシュ hit 時は <30 ms |
| 日次処理量 | 1,000,000 メッセージ | バースト時 1.3× まで許容 |
| リスク集計更新 | T+5 min 以内 | k‑匿名性テーブル反映 |

---
## 9. キャパシティ & スケーリング
* ** CPU インスタンス**: 初期 2 Pods, vCPU 合計 8。Cloud Run Max‑Instances=6。 
* **Scale‑out**: リクエスト数または CPU 75 % 超過で新規 Pod 起動。 
* **Scale‑down**: 10 分アイドルで Pod 0 に戻す（コスト最適）。 
* Redis は 1 GB→3 GB へオンラインアップグレード可能。 
* Pub/Sub は自動シャーディング、サブスクの max_outstanding_messages でバックプレッシャ管理。

---
## 10. セキュリティ & コンプライアンス
1. **ネットワーク** – VPC Service Controls, Private Service Connect で社内 API のみ許可。
2. **データ保護** – GCS バケット暗号化 (CMEK)、ログは 180 日後自動削除。(個情委ガイドライン準拠)
3. **IAM** – least privilege。Cloud Run → Pub/Sub → Storage まで Service Account 連鎖。
4. **モニタリング** – Cloud Audit Logs 必須。PII はマスク後でのみ永続化。
5. **ペネトレーションテスト** – 年 1 回実施、SOC2 Type2 を将来的に取得予定。

---
## 11. 運用
| 項目 | 内容 |
|------|------|
| デプロイ | Cloud Build → Artifact Registry → Cloud Run (blue/green) |
| 監視 | Cloud Monitoring、エラーレート >2 % /5 min で PagerDuty |
| バックアップ | DuckDB ファイルを日次 Cloud Storage Snapshot |
| 障害対応 | RTO 30 min、RPO 5 min (Pub/Sub 再配送) |

---
## 12. ビルド & デプロイ
本プロジェクトは依存関係の管理に `Poetry` を、コンテナ化に `Docker` を使用する。

### 12.1 依存関係のインストール
ローカルでの開発やテストの際は、Poetry を使って依存関係をインストールする。

```bash
# Poetry がインストールされていない場合
# curl -sSL https://install.python-poetry.org | python3 -

# 依存関係のインストール (開発用も含む)
poetry install
```

### 12.2 コンテナのビルドと実行
`Dockerfile` を使ってコンテナイメージをビルドし、ローカルで実行できる。

```bash
# Docker イメージのビルド
docker build -t pii-masking-api:latest .

# ローカルでのコンテナ実行
docker run -p 8080:8080 pii-masking-api:latest
```

### 12.3 Cloud Run へのデプロイ
Cloud Build を経由して Artifact Registry にイメージを push し、Cloud Run にデプロイする。このプロセスは `cloudbuild.yaml` (本書のスコープ外) によって自動化されることを想定する。

---
## 13. コスト試算（月額）
| リソース | 数量・時間 | 単価 (JPY) | 小計 |
|----------|-----------|-----------|--------|
| Cloud Run (e2‑std‑4) | 200 vCPUh + 400 GiBh | ¥0.033/vCPUh, ¥0.0036/GiBh | ≈ ¥8,000 |
| Cloud Run req 課金 | 2.6 M xreq | ¥0.40/1M | ¥1,040 |
| Memorystore (Redis) | 1 GB | ¥9,000 | ¥9,000 |
| Pub/Sub | 2 M msg | ¥0.40/1M | ¥800 |
| Cloud Storage (Cold) | 30 GB | ¥0.025/GB | ¥750 |
| Cloud Monitoring | – | ¥0.258/GB (logs) | ¥1,500 |
| **合計** | – | – | **≈ ¥21,000 / 月** |

> *金額は 2025/06 時点の東京リージョン公開価格をベースに算出。*

---
## 14. リスク & 今後の拡張
1. **高トラフィック急増時** → BERT‑base GPU へのフォールバック手段を検討 (Vertex AI)。
2. **モデル劣化** → 半年毎に追加ファインチューニング or 蒸留再学習計画。
3. **規制更新** → 個情法改正・新ガイドラインが出た際の閾値変更を容易に。

---
## 15. 承認フロー
| ステップ | 担当 | ステータス |
|-----------|------|--------------|
| ドキュメントレビュー | SRE / Data プラットフォーム | 2025‑06‑xx 担当者確認中 |
| コスト承認 | 経営企画 | – |
| セキュリティ審査 | CISO チーム | – |
| 本番リリース | インフラ責任者 | – |

