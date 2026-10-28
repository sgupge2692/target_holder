"""
APIレート制限 — slowapi + Redis / メモリフォールバック

制限値:
  - 認証系（login / register / password-reset）: 10回/分
  - シグナル取得（未認証のアクセス）: 30回/分
  - 一般API: 120回/分

REDIS_URL が設定されていれば Redis バックエンドを使用（分散環境対応）
未設定時はメモリバックエンド（シングルプロセス向け）
"""
import os
from slowapi import Limiter
from slowapi.util import get_remote_address

REDIS_URL = os.getenv("REDIS_URL", "")

if REDIS_URL:
    # Redisバックエンド（本番推奨）
    storage_uri = REDIS_URL
else:
    # メモリバックエンド（開発・シングルノード）
    storage_uri = "memory://"

limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=storage_uri,
    default_limits=["120/minute"],
)
