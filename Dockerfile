FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080 \
    GOOGLE_GENAI_USE_VERTEXAI=TRUE

RUN apt-get update && apt-get install -y --no-install-recommends \
    nginx \
    ca-certificates \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN pip install --no-cache-dir \
    streamlit>=1.38.0 \
    google-genai>=1.0.0 \
    google-cloud-bigquery>=3.25.0 \
    google-cloud-discoveryengine>=0.13.0 \
    websockets>=13.0 \
    certifi>=2024.0.0 \
    pydantic>=2.7.0

COPY . /app

RUN chmod +x /app/entrypoint.sh

EXPOSE 8080

CMD ["/app/entrypoint.sh"]
