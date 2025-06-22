# PII Masking Pipeline

A lightweight CPU-based Personal Identifiable Information (PII) masking pipeline for Japanese text processing.

## Features

- **NER-based Detection**: Uses ONNX Runtime with optimized models for entity recognition
- **Regex Pattern Matching**: Detects phone numbers, email addresses, postal codes, and MyNumber
- **Japanese Language Support**: Integrated with Sudachi tokenizer for accurate Japanese text processing
- **Risk Scoring**: Calculates risk scores based on detected PII types
- **Caching**: Built-in memory cache for improved performance
- **FastAPI Integration**: Ready-to-use REST API endpoints

## Installation

```bash
# Clone the repository
git clone <repository-url>
cd piipjt

# Install with Poetry
poetry install

# Or install with pip
pip install -e .
```

## Quick Start

```bash
# Run the demo
poetry run python demo.py

# Start the API server
poetry run uvicorn src.pii_masking.api.main:app --reload

# Or use the convenience script
poetry run python run_api.py
```

## Usage

### Basic Usage

```python
from pii_masking.core.pipeline import MaskingPipeline

# Initialize pipeline
pipeline = MaskingPipeline()

# Mask text
result = pipeline.mask_text("田中さんの電話番号は03-1234-5678です。")

print(result.masked_text)  # <MASK>さんの電話番号は<MASK>です。
print(result.risk_score)   # 0.70
print(result.entities)     # [Entity(text='田中', label='PERSON'), ...]
```

### API Server

```bash
# Start the FastAPI server
poetry run uvicorn src.pii_masking.api.main:app --reload

# Or use the convenience script
poetry run python run_api.py

# Access API documentation
# http://localhost:8000/docs
```

### API Usage

```bash
# Mask text via API
curl -X POST "http://localhost:8000/mask" \
     -H "Content-Type: application/json" \
     -d '{"text": "田中さんの電話番号は03-1234-5678です。"}'

# Response:
# {
#   "masked_text": "<MASK>さんの電話番号は<MASK>です。",
#   "entities": [{"text": "田中", "label": "PERSON"}],
#   "risk_score": 0.7,
#   "cached": false
# }
```

## Supported PII Types

- **Named Entities**: Person names, organizations, locations
- **Contact Information**: Phone numbers, email addresses
- **Identifiers**: Postal codes, MyNumber (Japanese national ID)

## Configuration

Configuration can be customized via environment variables or by modifying `src/pii_masking/config/settings.py`.

## Development

```bash
# Run tests
poetry run pytest

# Run linting
poetry run flake8
poetry run mypy src/

# Format code
poetry run black src/ tests/
poetry run isort src/ tests/
```

## License

[License information here]