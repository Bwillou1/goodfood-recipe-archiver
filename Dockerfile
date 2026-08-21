# ==============================================================================
#  Dockerfile sécurisé, léger & durci pour Goodfood Recipe Archiver
#  - Exécution en utilisateur non-root (appuser: 1000)
#  - Dépendances Chromium minimales (sans polices CJK géantes)
# ==============================================================================

FROM python:3.11-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    DEBIAN_FRONTEND=noninteractive \
    GOODFOOD_NO_SANDBOX=1

# 1. Bibliothèques système minimales pour Chromium
RUN apt-get update && apt-get install -y --no-install-recommends \
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

# 2. Utilisateur non-root sécurisé
RUN groupadd -g 1000 appuser && \
    useradd -u 1000 -g appuser -m -s /bin/bash appuser

WORKDIR /app

# 3. Installation des dépendances Python et de Chromium Playwright
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt && \
    playwright install chromium

# 4. Copie du code source et permissions
COPY config/ /app/config/
COPY src/ /app/src/
COPY scripts/ /app/scripts/
COPY run.py /app/

RUN mkdir -p /app/data/receipts /app/data/recipes /app/data/output /app/data/cache /app/cookies /app/logs && \
    chown -R appuser:appuser /app

USER appuser

ENTRYPOINT ["python", "run.py"]
