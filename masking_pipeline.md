# PII マスキングパイプライン — 技術解説

この資料は **マスキング処理そのもの** に絞り、リクエストが <MASK> 付きレスポンスになるまでの技術的ステップを明快に説明します。インフラや運用は別資料を参照してください。

---

## 1. 処理フロー概要

```
(text ≤1 KB)
   ↓ ①入力検証
   ↓ ②キャッシュ照会 ──┐  ヒット → レスポンス
   ↓ ③Regex 置換        │  ミス → 続行
   ↓ ④形態素解析         │
   ↓ ⑤NER 推論           │
   ↓ ⑥NER マスキング     │
   ↓ ⑦リスクスコア計算   │
   ↓ ⑧キャッシュ保存 ───┘
   ↓ ⑨Pub/Sub 発行（統計用）
   → レスポンス(JSON)
```

各ステップは **最小コストで抜け漏れなく PII を潰す** ために配置されています。

---

## 2. ステップ詳細

| # | ステップ           | 主要ライブラリ/設定                                                           | 処理時間 (P95)   | 要点                                                   |
| - | -------------- | -------------------------------------------------------------------- | ------------ | ---------------------------------------------------- |
| 1 | **入力検証**       | pydantic (FastAPI)                                                   | <1 ms        | 1 ≤ len(text) ≤ 1024 bytes を保証。                      |
| 2 | **キャッシュ照会**    | Redis (`GET sha256(text)`)                                           | <1 ms        | ヒット時は以降を全スキップ・`cached=true`。                         |
| 3 | **Regex 置換**   | re2 / Hyperscan                                                      | 3–5 ms       | \b0\d{1,3}-... など“定型 PII”。先に削ることで NER の負荷↓。          |
| 4 | **形態素解析**      | SudachiPy (core dict)                                                | 8–12 ms      | 日本語に必要。token ID は subword にしないと BERT が誤検出。           |
| 5 | **NER 推論**     | DistilBERT‑JP INT8 on ONNX Runtime<br>`session.run(None, np_inputs)` | 25–40 ms     | 蒸留 + INT8 量子化 + AVX2/512 で GPU 無しでも高速。               |
| 6 | **NER マスキング**  | Python post‑process                                                  | 1–2 ms       | `IOB2`→span→`<MASK>`に置換。重複を避けるため Regex 置換後のオフセットで処理。 |
| 7 | **リスクスコア**     | 関数 `compute_risk_score`                                              | <1 ms        | PERSON 件数 + Regex 種類で 0.2–1.0。                       |
| 8 | **キャッシュ保存**    | Redis (`SETEX 24h`)                                                  | <1 ms        | 同一文頻出を想定したコスト最適化。                                    |
| 9 | **Pub/Sub 発行** | google-cloud-pubsub                                                  | 3–5 ms (非同期) | k-匿名性用バッチに流す。API レイテンシには含めず。                         |

**合計 P95 ≈ 40–60 ms (cache miss)** / **<10 ms (cache hit)**。

---

## 3. コンポーネント技術メモ

### 3.1 Regex レイヤ

* re2 はスレッドセーフ・DFA 落ちしない。
* パターン追加は `regex_patterns.yaml` を編集→Poetry test で CI が syntax チェック。

### 3.2 SudachiPy

* Docker 層で `sudachipy link -t core` 実行済み。辞書更新時はコンテナ再ビルド必須。

### 3.3 DistilBERT‑JP INT8

* Apache‑2.0。量子化済みモデルは `models/distilbert-jp-int8.onnx`。
* 冷スタート対策で Cloud Run `min-instances=1`。
* コンテナ環境変数 `OMP_NUM_THREADS=1`, `ORT_INTRA_OP=4` がデフォルト。

### 3.4 キャッシュ設計

```
key   = sha256(text)
value = gzip(JSON response)
TTL   = 86400 (24h)
```

* メモリ枯渇時は LRU。TTL 更新は行わない（最長 24h）。

### 3.5 エラー処理

| レイヤ     | 想定例外                   | ハンドリング                    |
| ------- | ---------------------- | ------------------------- |
| Regex   | re.error               | 起動時 CI で検知。run 時は発生しない設計。 |
| Sudachi | DictionaryCorruptError | 500 を返しアラート。              |
| ONNX    | InvalidGraph, RunFail  | モデル再ロードを 1 回リトライ→失敗で 500。 |

---

## 4. 拡張ポイント

1. **PII タイプ追加** ─ Regex パターン & Enum 更新。<5 行で済む。
2. **モデル差し替え** ─ `models/` に新 .onnx を置き、`MODEL_PATH` 環境変数で指定。
3. **GPU モード** ─ ONNX Runtime に CUDA EP を追加し、Cloud Run GPU Revision を作れば OK。

---

## 5. テスト

* 単体テスト: `tests/test_masking.py` が 50 ケースを Parametrize。
* ベンチ: `scripts/bench.py -n 1000` が P95 出力。CI に含む。

---

## 6. まとめ

> **高速化の要** は「Regex で定型 PII を先に潰し、BERT は軽量 INT8・最小バッチで回す」こと。<MASK> さえ返せば機密は漏れません。

以降の保守は **Regex パターン管理** と **モデルリフレッシュ** の 2 点に集中すれば大半の問題を回避できます。
