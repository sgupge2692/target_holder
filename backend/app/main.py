import os
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.routers import auth, billing, signals, stocks, summary, notifications, admin, watchlist
from app.limiter import limiter
from app.metrics import metrics_output
from app.middleware import MetricsMiddleware

# ── Sentry エラー監視（SENTRY_DSN が設定されている場合のみ有効）─────────────
SENTRY_DSN = os.getenv("SENTRY_DSN", "")
if SENTRY_DSN:
    import sentry_sdk
    from sentry_sdk.integrations.fastapi import FastApiIntegration
    from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[
            FastApiIntegration(transaction_style="endpoint"),
            SqlalchemyIntegration(),
        ],
        traces_sample_rate=0.1,   # パフォーマンス計測: 10% サンプリング
        profiles_sample_rate=0.1,
        environment=os.getenv("ENV", "development"),
        release=os.getenv("RELEASE", "unknown"),
    )

app = FastAPI(
    title="Stock Intelligence API",
    description="株価予測・企業要約サービスのAPI",
    version="0.3.0",
)

# レート制限ミドルウェア
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# CORS: 本番では CORS_ORIGINS 環境変数でドメインを追加
_raw_origins = os.getenv("CORS_ORIGINS", "http://localhost:3000")
ALLOWED_ORIGINS = [o.strip() for o in _raw_origins.split(",") if o.strip()]

app.add_middleware(MetricsMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(billing.router)
app.include_router(signals.router)
app.include_router(stocks.router)
app.include_router(summary.router)
app.include_router(notifications.router)
app.include_router(admin.router)
app.include_router(watchlist.router)


@app.get("/health")
async def health_check():
    return {"status": "ok", "sentry": bool(SENTRY_DSN)}


# METRICS_TOKEN が設定されている場合は Bearer 認証を要求（任意）
_METRICS_TOKEN = os.getenv("METRICS_TOKEN", "")

@app.get("/metrics")
async def prometheus_metrics(request: Request):
    """Prometheus スクレイプ用エンドポイント"""
    if _METRICS_TOKEN:
        auth_header = request.headers.get("Authorization", "")
        if auth_header != f"Bearer {_METRICS_TOKEN}":
            return Response(status_code=403, content="Forbidden")
    data, content_type = metrics_output()
    return Response(content=data, media_type=content_type)
