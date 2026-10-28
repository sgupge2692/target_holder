# ── Stage 1: ビルド ────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
# LightGBM/XGBoost はビルド時間がかかるのでキャッシュを最大化
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt


# ── Stage 2: 本番イメージ ─────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /install /usr/local
COPY . .

RUN useradd -m -u 1000 mluser && chown -R mluser:mluser /app
USER mluser

CMD ["python", "pipeline/fetch_data.py"]
