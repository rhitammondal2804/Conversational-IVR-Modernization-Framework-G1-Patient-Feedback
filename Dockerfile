# ─────────────────────────────────────────────────────────────────────────────
# Dockerfile — Patient Feedback IVR
# Milestone 4: Deployment
# ─────────────────────────────────────────────────────────────────────────────

FROM python:3.11-slim

LABEL maintainer="Rhitam Mondal"
LABEL project="Conversational IVR Modernization Framework - G1 Patient Feedback"
LABEL milestone="4 - Deployment"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FLASK_ENV=production \
    PORT=5000

WORKDIR /app

# Install curl for HEALTHCHECK
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Dependencies first (Docker layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copy M3 source code
COPY src/ ./src/
COPY app.py .
COPY configs/ ./configs/

# Create data dir for feedback JSON storage
RUN mkdir -p /app/data

# Non-root user for security
RUN useradd -m -u 1000 ivruser && chown -R ivruser:ivruser /app
USER ivruser

EXPOSE 5000

# Health check hits the /api/health endpoint from simulator_app.py
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:5000/api/health || exit 1

# Production: gunicorn with 4 workers pointing at app.py's Flask app
CMD ["gunicorn", \
     "--bind", "0.0.0.0:5000", \
     "--workers", "4", \
     "--timeout", "120", \
     "--access-logfile", "-", \
     "--error-logfile", "-", \
     "app:app"]
