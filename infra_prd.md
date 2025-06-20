# PII マスキング基盤 — インフラ要件定義書

## 1. 目的
本書は、日本語テキストを対象とする PII（個人識別情報）マスキング API の軽量 CPU スタックに関し、インフラストラクチャ要件を定義する。目標は GPU 非依存で実用的な処理性能とコスト効率を両立し、企業内チャット／ドキュメント処理で日次 100 万メッセージ規模を安全にハンドリングすること。

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
## 4. コンポーネント要件
| # | コンポーネント | 技術/サービス | サイズ & 設定 | 可用性 | 補足 |
|---|--------------|---------------|---------------|--------|------|
| 1 | **API 層** | Cloud Run (container) | `e2-standard-4` ×2, auto-scale 0–6 | 99.5 % | FastAPI + Uvicorn、10 MiB メモリバッファ |
| 2 | **Regex レイヤ** | re2 ライブラリ | 同上 | – | Hyperscan 置換可 |
| 3 | **Tokenizer** | SudachiPy (core dict) | 同上 | – | MeCab 互換辞書不要 |
| 4 | **NER 推論** | ONNX Runtime INT8、モデル: `line-distilbert-base-japanese` | 同上 | – | 25–40 ms/1k 字 (P95) |
| 5 | **キャッシュ** | Cloud Memorystore (Redis) | 1 GB、max‑memory‑policy allkeys‑lru | 99.9 % | TTL 24 h、推論結果キー=SHA‑256(input) |
| 6 | **メッセージキュー** | Pub/Sub Topic + Subscription | 7 日保持, Ack deadline 60 s | 99.9 % | ストリームバッファ兼バックプレッシャ |
| 7 | **リスク集計** | Cloud Run Job → DuckDB | `e2-standard-4`, 1 job/min | – | parquet append; k=5, l=2, rarity スコア計算 |
| 8 | **ストレージ** | Cloud Storage (Coldline) | 30 GB 想定 | 99.99 % | 生ログ + マスク済みデータ保管 |
| 9 | **監視** | Cloud Monitoring & Logging | – | – | SLA/ErrorRate/GCS バケットサイズ等 |

---
## 5. 性能要件
| 指標 | 目標値 | 備考 |
|------|--------|------|
| 同時リクエスト | 80 RPS (平常), 200 RPS (ピーク5 min) | Auto‑scale 対応 |
| レイテンシ (P95) | ≤120 ms / 1 KB 入力 | キャッシュ hit 時は <30 ms |
| 日次処理量 | 1,000,000 メッセージ | バースト時 1.3× まで許容 |
| リスク集計更新 | T+5 min 以内 | k‑匿名性テーブル反映 |

---
## 6. キャパシティ & スケーリング
* ** CPU インスタンス**: 初期 2 Pods, vCPU 合計 8。Cloud Run Max‑Instances=6。 
* **Scale‑out**: リクエスト数または CPU 75 % 超過で新規 Pod 起動。 
* **Scale‑down**: 10 分アイドルで Pod 0 に戻す（コスト最適）。 
* Redis は 1 GB→3 GB へオンラインアップグレード可能。 
* Pub/Sub は自動シャーディング、サブスクの max_outstanding_messages でバックプレッシャ管理。

---
## 7. セキュリティ & コンプライアンス
1. **ネットワーク** – VPC Service Controls, Private Service Connect で社内 API のみ許可。
2. **データ保護** – GCS バケット暗号化 (CMEK)、ログは 180 日後自動削除。(個情委ガイドライン準拠)
3. **IAM** – least privilege。Cloud Run → Pub/Sub → Storage まで Service Account 連鎖。
4. **モニタリング** – Cloud Audit Logs 必須。PII はマスク後でのみ永続化。
5. **ペネトレーションテスト** – 年 1 回実施、SOC2 Type2 を将来的に取得予定。

---
## 8. 運用
| 項目 | 内容 |
|------|------|
| デプロイ | Cloud Build → Artifact Registry → Cloud Run (blue/green) |
| 監視 | Cloud Monitoring、エラーレート >2 % /5 min で PagerDuty |
| バックアップ | DuckDB ファイルを日次 Cloud Storage Snapshot |
| 障害対応 | RTO 30 min、RPO 5 min (Pub/Sub 再配送) |

---
## 9. コスト試算（月額）
| リソース | 数量・時間 | 単価 (JPY) | 小計 |
|----------|-----------|-----------|--------|
| Cloud Run (e2‑std‑4) | 200 vCPUh + 400 GiBh | ¥0.033/vCPUh, ¥0.0036/GiBh | ≈ ¥8,000 |
| Cloud Run req 課金 | 2.6 M xreq | ¥0.40/1M | ¥1,040 |
| Memorystore (Redis) | 1 GB | ¥9,000 | ¥9,000 |
| Pub/Sub | 2 M msg | ¥0.40/1M | ¥800 |
| Cloud Storage (Cold) | 30 GB | ¥0.025/GB | ¥750 |
| Cloud Monitoring | – | ¥0.258/GB (logs) | ¥1,500 |
| **合計** | – | – | **≈ ¥21,000 / 月** |

> *金額は 2025/06 時点の東京リージョン公開価格をベースに算出。*

---
## 10. リスク & 今後の拡張
1. **高トラフィック急増時** → BERT‑base GPU へのフォールバック手段を検討 (Vertex AI)。
2. **モデル劣化** → 半年毎に追加ファインチューニング or 蒸留再学習計画。
3. **規制更新** → 個情法改正・新ガイドラインが出た際の閾値変更を容易に。

---
## 11. 承認フロー
| ステップ | 担当 | ステータス |
|-----------|------|--------------|
| ドキュメントレビュー | SRE / Data プラットフォーム | 2025‑06‑xx 担当者確認中 |
| コスト承認 | 経営企画 | – |
| セキュリティ審査 | CISO チーム | – |
| 本番リリース | インフラ責任者 | – |

