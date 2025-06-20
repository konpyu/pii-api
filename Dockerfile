# --- 1. Builder Stage: Install dependencies with Poetry ---
FROM python:3.10-slim as builder

ENV POETRY_HOME="/opt/poetry"
ENV POETRY_VENV="/opt/venv"
ENV PATH="$POETRY_HOME/bin:$PATH"

# Install Poetry
RUN apt-get update && apt-get install -y curl && \
    curl -sSL https://install.python-poetry.org | python3 -

# Create a virtual environment
RUN python3 -m venv $POETRY_VENV

# Copy project definition
COPY pyproject.toml poetry.lock* ./

# Install dependencies into the virtual environment
# --no-dev: Do not install development dependencies
# --no-interaction: Do not ask any interactive questions
# --no-ansi: Disable ANSI output
RUN poetry install --no-dev --no-interaction --no-ansi

# --- 2. Runner Stage: Create the final, lean image ---
FROM python:3.10-slim as runner

ENV VIRTUAL_ENV="/opt/venv"
ENV PATH="$VIRTUAL_ENV/bin:$PATH"
ENV PORT=8080

# Copy the virtual environment from the builder stage
COPY --from=builder /opt/venv /opt/venv

# Set the working directory
WORKDIR /app

# Copy the application code
COPY pii_masking_api_app.py .

# Expose the port the app runs on
EXPOSE 8080

# Run the application
CMD ["uvicorn", "pii_masking_api_app:app", "--host", "0.0.0.0", "--port", "8080"] 