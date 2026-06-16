FROM python:3.13-slim

# Install uv (fast Python package manager)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Install dependencies first (cached layer)
COPY pyproject.toml ./
RUN uv sync --no-dev --frozen 2>/dev/null || uv sync --no-dev

# Copy application code
COPY app.py pages/ core/ templates/ assets/ ./
COPY pages/ ./pages/
COPY core/ ./core/
COPY templates/ ./templates/
COPY assets/ ./assets/

# Create non-root user (UID 1000, per container-deployment spec R9)
RUN useradd -m -u 1000 appuser && \
    mkdir -p /data /out /assets && \
    chown -R appuser:appuser /app /data /out /assets

USER appuser

EXPOSE 8501

# Healthcheck: Streamlit responds on port 8501
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health')" || exit 1

CMD ["uv", "run", "streamlit", "run", "app.py", \
     "--server.port=8501", \
     "--server.address=0.0.0.0", \
     "--server.headless=true"]
