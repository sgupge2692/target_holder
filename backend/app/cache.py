"""
Redis キャッシュユーティリティ

REDIS_URL が未設定の場合はキャッシュなし（スルー）で動作する。
使い方:
  from app.cache import cache_get, cache_set, cache_delete, cache_key

  val = await cache_get("my:key")
  if val is None:
      val = await expensive_query()
      await cache_set("my:key", val, ttl=300)
"""
import os
import json
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

REDIS_URL = os.getenv("REDIS_URL", "")

# Redis クライアント（遅延初期化）
_redis = None


async def _get_redis():
    global _redis
    if _redis is not None:
        return _redis
    if not REDIS_URL:
        return None
    try:
        import redis.asyncio as aioredis
        _redis = aioredis.from_url(REDIS_URL, decode_responses=True)
        await _redis.ping()
        return _redis
    except Exception as e:
        logger.warning(f"Redis connection failed: {e}. Caching disabled.")
        _redis = None
        return None


def _serialize(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def _deserialize(raw: str) -> Any:
    return json.loads(raw)


async def cache_get(key: str) -> Optional[Any]:
    """キャッシュから値を取得。ミス or Redisなし → None"""
    r = await _get_redis()
    if r is None:
        return None
    try:
        raw = await r.get(key)
        return _deserialize(raw) if raw is not None else None
    except Exception as e:
        logger.warning(f"cache_get error [{key}]: {e}")
        return None


async def cache_set(key: str, value: Any, ttl: int = 300) -> bool:
    """キャッシュに値をセット。ttl は秒。"""
    r = await _get_redis()
    if r is None:
        return False
    try:
        await r.setex(key, ttl, _serialize(value))
        return True
    except Exception as e:
        logger.warning(f"cache_set error [{key}]: {e}")
        return False


async def cache_delete(key: str) -> bool:
    r = await _get_redis()
    if r is None:
        return False
    try:
        await r.delete(key)
        return True
    except Exception as e:
        logger.warning(f"cache_delete error [{key}]: {e}")
        return False


async def cache_delete_pattern(pattern: str) -> int:
    """パターンにマッチするキーを一括削除（本番では SCAN ベース）"""
    r = await _get_redis()
    if r is None:
        return 0
    try:
        keys = await r.keys(pattern)
        if keys:
            return await r.delete(*keys)
        return 0
    except Exception as e:
        logger.warning(f"cache_delete_pattern error [{pattern}]: {e}")
        return 0


def cache_key(*parts: str) -> str:
    """キャッシュキー生成ヘルパー: cache_key("signals", "UP", "12") → "signals:UP:12" """
    return ":".join(str(p) for p in parts)
