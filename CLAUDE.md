# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a PII (Personally Identifiable Information) Masking API designed for Japanese text processing. It's a production-ready FastAPI service that detects and masks sensitive personal information using a lightweight CPU-based stack.

## Common Commands

### Development
```bash
# Install dependencies (requires Poetry)
poetry install

# Run the API server
uvicorn src.pii_masking.api.main:app --reload

# Run quick test
python quick_test.py

# Run demo
python demo.py
```

### Code Quality
```bash
# Format code
make format

# Run linter
make lint

# Type checking
make type-check

# Run all quality checks
make all
```

### Testing
```bash
# Run all tests
make test

# Run specific test markers
pytest -m unit        # Unit tests only
pytest -m integration # Integration tests only
pytest -m slow       # Slow tests only

# Run tests with coverage
pytest --cov=src/pii_masking
```

### Load Testing
```bash
# Run load tests using Locust
locust -f tests/locust/locustfile.py --host http://localhost:8000
```

## Architecture Overview

### Core Pipeline (`src/pii_masking/core/pipeline.py`)
The masking pipeline processes text through 9 steps:
1. Input validation
2. Text normalization
3. Regex-based PII detection (phone numbers, postal codes, etc.)
4. Japanese tokenization (SudachiPy)
5. Named Entity Recognition (DistilBERT-JP via ONNX)
6. Entity consolidation
7. Risk scoring
8. Masking application
9. Response generation

### Key Components
- **Cache Layer** (`src/pii_masking/cache/`): In-memory caching with SHA-256 keys for performance
- **Processors** (`src/pii_masking/processors/`): Modular processing components for each pipeline step
- **Config** (`src/pii_masking/config/`): YAML-based configuration for regex patterns and settings
- **Models** (`src/pii_masking/models/`): ONNX model loading utilities with INT8 quantization support

### API Design
- Main endpoint: `POST /mask` - Accepts text and returns masked version with metadata
- Performance targets: 80-200 RPS, <120ms P95 latency
- Deployment: Designed for Google Cloud Run with Redis caching and Pub/Sub integration

### Testing Strategy
- Unit tests for all individual components
- Integration tests for end-to-end pipeline validation
- Load testing with Locust for performance verification
- Test markers: `unit`, `integration`, `slow` for selective test execution