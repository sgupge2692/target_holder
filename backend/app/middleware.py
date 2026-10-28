"""
Prometheus メトリクス収集ミドルウェア

リクエスト数・レイテンシを自動記録します。
"""
import time
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from app.metrics import REQUEST_COUNT, REQUEST_LATENCY, ERROR_COUNT


# パスを正規化（/stocks/7203 → /stocks/{code} など）
_PATH_NORMALIZERS = [
    ("/stocks/", "/stocks/{code}"),
    ("/api/admin/users/", "/api/admin/users/{id}"),
]

def _normalize_path(path: str) -> str:
    for prefix, normalized in _PATH_NORMALIZERS:
        if path.startswith(prefix):
            return normalized
    return path


class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        # /metrics 自身は計測しない
        if request.url.path == "/metrics":
            return await call_next(request)

        start = time.perf_counter()
        endpoint = _normalize_path(request.url.path)
        method = request.method

        try:
            response = await call_next(request)
        except Exception:
            ERROR_COUNT.labels(endpoint=endpoint).inc()
            raise

        elapsed = time.perf_counter() - start
        status = str(response.status_code)

        REQUEST_COUNT.labels(method=method, endpoint=endpoint, status_code=status).inc()
        REQUEST_LATENCY.labels(method=method, endpoint=endpoint).observe(elapsed)

        if response.status_code >= 500:
            ERROR_COUNT.labels(endpoint=endpoint).inc()

        return response
