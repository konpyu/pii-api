"""
pii_masking_api_app.py – 概念実装
---------------------------------
軽量 CPU スタックを想定した FastAPI アプリ。
本番では Cloud Run / Cloud Functions 等にデプロイし、
Redis・Pub/Sub・DuckDB など GCP マネージドサービスに
置き換えることを前提とする。

依存:
  pip install fastapi uvicorn redis onnxruntime sudachipy duckdb google-cloud-pubsub

※ ONNX/NER 部分・Pub/Sub はモック実装。
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from typing import Dict, List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# --- 可搬レイヤ -------------------------------------------------------------
# Regex patterns (電話番号, 郵便番号, マイナンバー etc.)
REGEX_PATTERNS = [
    re.compile(r"\b0\d{1,3}-\d{1,4}-\d{4}\b"),  # 電話番号 03-1234-5678
    re.compile(r"\b\d{3}-\d{4}\b"),  # 郵便番号 123-4567
    re.compile(r"\b\d{3}\d{4}\d{4}\d{4}\b"),  # マイナンバー 1234567890123
]

# 簡易トークナイザ (SudachiPy 置き換え可)
try:
    from sudachipy import dictionary
    from sudachipy import tokenizer as sudachi_tokenizer

    _tokenizer_obj = dictionary.Dictionary().create()

    def tokenize(text: str) -> List[str]:
        return [
            m.surface()
            for m in _tokenizer_obj.tokenize(
                text, sudachi_tokenizer.Tokenizer.SplitMode.C
            )
        ]

except ModuleNotFoundError:

    def tokenize(text: str) -> List[str]:
        return text.split()


# Mock NER using gazetteer (本番では ONNX Runtime + DistilBERT INT8)
GAZETTEER_NAMES = {"佐藤", "鈴木", "高橋", "田中", "山田"}


def ner_entities(text: str) -> List[Dict[str, str]]:
    entities = []
    for token in tokenize(text):
        if token in GAZETTEER_NAMES:
            entities.append({"text": token, "label": "PERSON"})
    return entities


# Simple mask replacement
def apply_masks(text: str, entities: List[Dict[str, str]]) -> str:
    masked = text
    # Regex first
    for pattern in REGEX_PATTERNS:
        masked = pattern.sub("<MASK>", masked)
    # Entity mask
    for ent in entities:
        masked = masked.replace(ent["text"], "<MASK>")
    return masked


# Redis cache ---------------------------------------------------------------
REDIS_DSN = os.getenv("REDIS_URL", "redis://localhost:6379/0")
try:
    import redis.asyncio as redis_async

    redis_client: Optional[redis_async.Redis] = redis_async.from_url(REDIS_DSN)
except ModuleNotFoundError:
    redis_client = None


async def cache_get(key: str) -> Optional[str]:
    if redis_client is None:
        return None
    try:
        return await redis_client.get(key)
    except Exception:
        return None


async def cache_set(key: str, value: str, ttl: int = 60 * 60 * 24):
    if redis_client is None:
        return
    try:
        await redis_client.set(key, value, ex=ttl)
    except Exception:
        pass


# Pub/Sub mock (fire-and-forget) -------------------------------------------
PUBSUB_ENABLED = os.getenv("PUBSUB", "false").lower() == "true"
if PUBSUB_ENABLED:
    from google.cloud import pubsub_v1

    PUB_TOPIC = os.getenv("PUBSUB_TOPIC", "pii-risk-queue")
    _publisher = pubsub_v1.PublisherClient()
    _topic_path = _publisher.topic_path(os.getenv("GCP_PROJECT"), PUB_TOPIC)
else:
    _publisher = None
    _topic_path = None


def enqueue_for_risk_calc(record: dict):
    if _publisher is None:
        return
    data = json.dumps(record).encode()
    _publisher.publish(_topic_path, data=data)


# DuckDB risk score (placeholder) ------------------------------------------
DB_PATH = os.getenv("DUCKDB_PATH", "/tmp/pii_risk.duckdb")


def compute_risk_score(entities: List[Dict[str, str]]) -> float:
    """極簡単な個体識別リスク: PERSON エンティティ数で proxy"""
    persons = [e for e in entities if e["label"] == "PERSON"]
    # 人名が 0 -> 低リスク, 1 -> 中, 2 以上->高
    if len(persons) == 0:
        return 0.2
    if len(persons) == 1:
        return 0.6
    return 0.9


# FastAPI ------------------------------------------------------------------
app = FastAPI(title="CPU‑Only PII Masking API")


class MaskRequest(BaseModel):
    text: str


class MaskResponse(BaseModel):
    masked_text: str
    entities: List[Dict[str, str]]
    risk_score: float
    cached: bool


@app.post("/mask", response_model=MaskResponse)
async def mask_endpoint(req: MaskRequest):
    text = req.text
    if not text:
        raise HTTPException(status_code=400, detail="text is required")

    key = hashlib.sha256(text.encode()).hexdigest()
    cached_val = await cache_get(key)
    if cached_val:
        resp_dict = json.loads(cached_val)
        resp_dict["cached"] = True
        return resp_dict

    # 1. Regex + NER
    entities = ner_entities(text)
    masked = apply_masks(text, entities)

    # 2. Risk score (sync) & enqueue for batch risk aggregation (async)
    risk_score = compute_risk_score(entities)
    enqueue_for_risk_calc({"entities": entities, "risk_score": risk_score})

    resp = {
        "masked_text": masked,
        "entities": entities,
        "risk_score": risk_score,
        "cached": False,
    }

    # 3. Cache
    await cache_set(key, json.dumps(resp))
    return resp


# uvicorn エントリ point
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "pii_masking_api_app:app", host="0.0.0.0", port=int(os.getenv("PORT", 8080))
    )
