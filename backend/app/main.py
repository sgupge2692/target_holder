from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import os

from .routers import signals, stocks


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 起動時処理（DB接続確認など）
    yield
    # 終了時処理


app = FastAPI(
    title="Stock Intelligence API",
    description="日本株AI予測・企業要約サービスのAPI",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        os.getenv("FRONTEND_URL", "http://localhost:3000"),
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(signals.router, prefix="/api")
app.include_router(stocks.router,  prefix="/api")


@app.get("/health")
async def health_check():
    return {"status": "ok", "version": "0.1.0"}
