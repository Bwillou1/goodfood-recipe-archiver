# ==============================================================================
#  Dockerfile sécurisé & durci pour Goodfood Recipe Archiver
#  - Exécution en utilisateur non-root (appuser: 1000)
#  - Isolation du code source
# ==============================================================================

FROM python:3.11-slim-bookworm

# 1. Variables d'environnement de sécurité
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    DEBIAN_FRONTEND=noninteractive

# 2. Installation des dépendances système (Tesseract OCR, Playwright runtime)
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-fra \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2 \
    fonts-liberation \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# 3. Création de l'utilisateur non-root sécurisé
RUN groupadd -g 1000 appuser && \
    useradd -u 1000 -g appuser -m -s /bin/bash appuser

WORKDIR /app

# 4. Installation des dépendances Python
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt && \
    playwright install chromium

# 5. Copie du code source et configuration des permissions
COPY config/ /app/config/
COPY src/ /app/src/
COPY run.py /app/

RUN mkdir -p /app/data/receipts /app/data/recipes /app/data/output /app/cookies /app/logs && \
    chown -R appuser:appuser /app

# 6. Bascule vers l'utilisateur non-root
USER appuser

ENTRYPOINT ["python", "run.py"]
