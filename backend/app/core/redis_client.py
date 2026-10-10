# Copyright (C) 2026 CenkorProcess Project
# SPDX-License-Identifier: AGPL-3.0
"""Redis 连接（可选）；未安装 redis 库或连不上时返回 None，调用方自行降级。"""

from __future__ import annotations

import logging

from app.core.config import settings

logger = logging.getLogger(__name__)

try:  # redis 在 requirements 中声明，但未安装/未运行时不阻断导入
    import redis
except Exception:  # noqa: BLE001
    redis = None  # type: ignore[assignment]

_client: "redis.Redis | None | bool" = None


def get_redis():
    """返回可用的 redis.Redis 客户端；任何不可用情形返回 None（且不重复报错）。"""
    global _client
    if redis is None:
        return None
    if _client is False:
        return None
    if _client is not None:
        return _client
    try:
        c = redis.from_url(settings.REDIS_URL, decode_responses=True)
        c.ping()
        _client = c
        return c
    except Exception as exc:  # noqa: BLE001 - 连不上则标记不可用，降级
        logger.info("Redis 不可用(%s)，相关能力降级", exc)
        _client = False
        return None
