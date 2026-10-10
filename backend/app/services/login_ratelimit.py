# Copyright (C) 2026 CenkorProcess Project
# SPDX-License-Identifier: AGPL-3.0
"""登录失败限流（内存滑动窗口，单机足够；无 Redis 时降级）。"""
from __future__ import annotations

import time
from threading import Lock

from app.core.config import settings

_key = "cenkormes:login_fail:"
_mem: dict[str, list[float]] = {}
_lock = Lock()


def _enabled() -> bool:
    return int(settings.LOGIN_MAX_FAILURES) > 0


def is_login_blocked(ip: str | None) -> bool:
    if not _enabled():
        return False
    if not ip:
        return False
    now = time.time()
    window = float(settings.LOGIN_FAIL_WINDOW_SECONDS)
    lockout = float(settings.LOGIN_LOCKOUT_SECONDS)
    with _lock:
        _prune(now)
        key = _key + ip
        failures = [t for t in _mem.get(key, []) if t > now - window]
        return len(failures) >= int(settings.LOGIN_MAX_FAILURES) and (failures[-1] > now - lockout)


def record_login_failure(ip: str | None) -> None:
    if not _enabled() or not ip:
        return
    now = time.time()
    with _lock:
        _prune(now)
        key = _key + ip
        _mem.setdefault(key, []).append(now)


def reset_login_failures(ip: str | None) -> None:
    if not ip:
        return
    with _lock:
        _mem.pop(_key + ip, None)


def _prune(now: float) -> None:
    window = float(settings.LOGIN_FAIL_WINDOW_SECONDS)
    for key in list(_mem):
        _mem[key] = [t for t in _mem[key] if t > now - window]
        if not _mem[key]:
            del _mem[key]