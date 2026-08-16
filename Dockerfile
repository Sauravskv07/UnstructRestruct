FROM node:20-bookworm-slim AS frontend
WORKDIR /ui
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim-bookworm
RUN apt-get update \
    && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt
COPY backend/ /app/backend/
COPY --from=frontend /ui/dist /app/frontend/dist
COPY sample_documents/ /app/sample_documents/

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/backend
ENV DATABASE_URL=sqlite:////data/app.db
ENV UPLOAD_DIR=/data/uploads
ENV CORS_ORIGINS=*
ENV LLM_MODE=auto
ENV PORT=8000

WORKDIR /app/backend
EXPOSE 8000

CMD ["sh", "-c", "mkdir -p /data/uploads && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
