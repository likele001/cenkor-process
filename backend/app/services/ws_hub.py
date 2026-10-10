# Copyright (C) 2026 CenkorProcess Project
# SPDX-License-Identifier: AGPL-3.0
"""WebSocket 连接池：向已订阅客户端推送看板刷新 / 预警 / 关键变更事件。

生产者在同步代码里（线程池中的 FastAPI 端点、脚本），消费者在事件循环里，
因此广播必须经 run_coroutine_threadsafe 回主循环。

连接池是进程内存态：多 worker 部署时每台只有自己连接的客户端；跨进程需换
Redis pub/sub（见 core/redis_client）。当前默认单进程，先不做这层。
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
from typing import Any, Iterable

from fastapi import WebSocket

logger = logging.getLogger(__name__)

# 连续提交不该让大屏重载几十遍：合并窗口内的多次变更累计后补发一次
REFRESH_COALESCE_SECONDS = 3.0


class WSHub:
    def __init__(self) -> None:
        self._clients: set[WebSocket] = set()
        self._lock = asyncio.Lock()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._sync = threading.Lock()
        self._pending_channels: set[str] = set()
        self._last_flush_at = 0.0
        self._flush_handle: asyncio.TimerHandle | None = None

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self._loop = asyncio.get_running_loop()
        async with self._lock:
            self._clients.add(ws)

    async def disconnect(self, ws: WebSocket) -> None:
        async with self._lock:
            self._clients.discard(ws)

    @property
    def client_count(self) -> int:
        return len(self._clients)

    async def broadcast(self, payload: dict[str, Any]) -> None:
        async with self._lock:
            targets = list(self._clients)
        if not targets:
            return
        text = json.dumps(payload, ensure_ascii=False, default=str)
        dead: list[WebSocket] = []
        for ws in targets:
            try:
                await ws.send_text(text)
            except Exception:  # noqa: BLE001 - 发送失败即剔除该连接
                dead.append(ws)
        if dead:
            async with self._lock:
                for ws in dead:
                    self._clients.discard(ws)

    def publish(self, payload: dict[str, Any]) -> None:
        """从任意线程投递一条消息，绝不抛出（推送失败不该拖垮业务写入）。"""
        loop = self._loop
        if loop is None or not self._clients or loop.is_closed():
            return
        try:
            asyncio.run_coroutine_threadsafe(self.broadcast(payload), loop)
        except RuntimeError as e:  # noqa: BLE001
            logger.debug("ws publish skipped: %s", e)

    def publish_refresh(
        self,
        channels: Iterable[str] = (),
        *,
        reason: str = "",
        coalesce: bool = True,
    ) -> bool:
        """投递刷新事件；返回是否立刻发出（False = 已合并或无人订阅）。"""
        if not self._clients:
            return False
        names = {c for c in channels if c} or {"dashboard"}
        now = time.monotonic()
        with self._sync:
            self._pending_channels |= names
            wait = self._last_flush_at + REFRESH_COALESCE_SECONDS - now
            if not coalesce or wait <= 0:
                return self._flush_locked(now, reason)
            self._schedule_flush_locked(wait, reason)
            return False

    def _schedule_flush_locked(self, delay: float, reason: str) -> None:
        loop = self._loop
        if loop is None or loop.is_closed():
            return
        self._flush_handle = None
        try:
            self._flush_handle = loop.call_later(delay, lambda: self.publish_refresh_scheduled(reason))
        except RuntimeError as e:  # noqa: BLE001
            logger.debug("ws coalesce schedule skipped: %s", e)

    def publish_refresh_scheduled(self, reason: str = "coalesced") -> None:
        with self._sync:
            self._flush_handle = None
            self._flush_locked(time.monotonic(), reason)

    def _flush_locked(self, now: float, reason: str) -> bool:
        if not self._pending_channels:
            return False
        payload: dict[str, Any] = {
            "type": "refresh",
            "channel": "dashboard",
            "changed": sorted(self._pending_channels),
        }
        if reason:
            payload["reason"] = reason
        self._pending_channels = set()
        self._last_flush_at = now
        self.publish(payload)
        return True


ws_hub = WSHub()
