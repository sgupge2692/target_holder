FROM python:3.11-slim

WORKDIR /app

# システム依存ライブラリ
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libpq-dev \
    wget \
    curl \
    && rm -rf /var/lib/apt/lists/*

# TA-Lib C ライブラリをインストール
# SourceForgeは不安定なのでGitHub mirrorから取得
RUN wget -q https://github.com/TA-Lib/ta-lib/releases/download/v0.5.1/ta-lib-0.5.1-src.tar.gz \
    && tar -xzf ta-lib-0.5.1-src.tar.gz \
    && cd ta-lib-0.5.1 \
    && ./configure --prefix=/usr \
    && make -j$(nproc) \
    && make install \
    && cd .. \
    && rm -rf ta-lib-0.5.1 ta-lib-0.5.1-src.tar.gz \
    && ldconfig

# Python依存ライブラリ
COPY requirements.txt .
RUN pip install --no-cache-dir --break-system-packages -r requirements.txt 2>/dev/null \
    || pip install --no-cache-dir -r requirements.txt

# データ・モデル保存ディレクトリ
RUN mkdir -p /app/models /app/data

# アプリケーションコードをコピー
COPY . .

CMD ["python", "pipeline/fetch_data.py"]
