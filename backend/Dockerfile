FROM python:3.12-slim

ARG INSTALL_OCR=false
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1
WORKDIR /app

RUN if [ "$INSTALL_OCR" = "true" ]; then \
      apt-get update && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-eng tesseract-ocr-chi-sim && \
      rm -rf /var/lib/apt/lists/*; \
    fi
COPY backend/requirements.txt ./requirements.txt
COPY backend/requirements-ocr.txt ./requirements-ocr.txt
RUN python -m pip install -r requirements.txt
RUN if [ "$INSTALL_OCR" = "true" ]; then python -m pip install -r requirements-ocr.txt; fi
RUN useradd --create-home --uid 10001 appuser && mkdir -p /app/.data/objects && chown -R appuser:appuser /app/.data
COPY --chown=appuser:appuser backend/app ./app
USER appuser
EXPOSE 8000
# Container listens on its own interface; compose publishes only to host loopback.
CMD ["python", "-m", "uvicorn", "app.core.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
