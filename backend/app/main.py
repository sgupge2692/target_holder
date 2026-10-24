from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import auth, billing, signals, stocks, summary

app = FastAPI(
    title="Stock Intelligence API",
    description="株価予測・企業要約サービスのAPI",
    version="0.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(billing.router)
app.include_router(signals.router)
app.include_router(stocks.router)
app.include_router(summary.router)


@app.get("/health")
async def health_check():
    return {"status": "ok"}
