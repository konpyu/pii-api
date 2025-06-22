"""FastAPI application for PII masking service."""

import logging
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, validator

from ..core.pipeline import MaskingPipeline

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="PII Masking API",
    description="API for masking personally identifiable information in Japanese text",
    version="1.0.0",
)

# Initialize masking pipeline
pipeline: Optional[MaskingPipeline] = None
try:
    pipeline = MaskingPipeline()
    logger.info("Masking pipeline initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize pipeline: {e}")


# Request/Response models
class MaskRequest(BaseModel):
    """Request model for masking endpoint."""

    text: str = Field(
        ..., description="Text to be masked", min_length=1, max_length=1024
    )

    @validator("text")
    def validate_text_bytes(cls, v: str) -> str:
        """Validate text is within byte limits."""
        if len(v.encode("utf-8")) > 1024:
            raise ValueError("text exceeds 1024 bytes")
        return v


class Entity(BaseModel):
    """Detected entity information."""

    text: str = Field(..., description="Original entity text")
    label: str = Field(..., description="Entity type label")


class MaskResponse(BaseModel):
    """Response model for masking endpoint."""

    masked_text: str = Field(..., description="Text with PII masked")
    entities: List[Entity] = Field(..., description="List of detected entities")
    risk_score: float = Field(..., description="Risk score (0.0-1.0)")
    cached: bool = Field(..., description="Whether response was served from cache")


# Health check endpoint
@app.get("/")
async def health_check() -> Dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy", "service": "pii-masking-api"}


# Main masking endpoint
@app.post("/mask", response_model=MaskResponse)
async def mask_text(request: MaskRequest) -> MaskResponse:
    """
    Mask PII in the provided text.

    Args:
        request: MaskRequest containing text to be masked

    Returns:
        MaskResponse with masked text and metadata

    Raises:
        400: Invalid request (empty text, too long)
        500: Internal server error
    """
    # Check if pipeline is initialized
    if pipeline is None:
        logger.error("Pipeline not initialized")
        raise HTTPException(status_code=500, detail="Internal server error")

    try:
        # Validate text
        if not request.text or request.text.isspace():
            raise HTTPException(status_code=400, detail="text is required")

        # Process text through pipeline
        result = pipeline.mask_text(request.text)

        # Convert entities to response format
        entities = [
            Entity(text=entity.text, label=entity.label) for entity in result.entities
        ]

        # Return response
        return MaskResponse(
            masked_text=result.masked_text,
            entities=entities,
            risk_score=result.risk_score,
            cached=result.cached,
        )

    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        # Log unexpected errors
        logger.error(f"Error processing request: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# Error handlers
@app.exception_handler(422)
async def validation_exception_handler(request: Request, exc: Any) -> JSONResponse:
    """Handle validation errors."""
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors()},
    )


@app.exception_handler(500)
async def internal_error_handler(request: Request, exc: Any) -> JSONResponse:
    """Handle internal server errors."""
    logger.error(f"Internal error: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )
