# Copyright (C) 2026 CenkorProcess Project
# SPDX-License-Identifier: AGPL-3.0
"""云存储凭据 AES-256-GCM 加解密（可选；仅在使用云端凭据配置时接线）。

密钥派生自现有 JWT_SECRET（不引入独立密钥体系）：
    key = SHA256(JWT_SECRET).digest()
密文格式：base64(nonce[12] | ciphertext | tag[16])
"""
from __future__ import annotations

import base64
import hashlib
import os

from app.core.config import settings

_NONCE_LEN = 12

try:  # cryptography 随 python-jose[cryptography] 传入；缺失时相关加解密降级不可用
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    _CRYPTO_AVAILABLE = True
except Exception:  # noqa: BLE001
    AESGCM = None  # type: ignore[assignment]
    _CRYPTO_AVAILABLE = False


def _keys() -> tuple[bytes, ...]:
    secrets = [
        getattr(settings, "JWT_SECRET", ""),
        getattr(settings, "JWT_SECRET_OLD", ""),
    ]
    return tuple(hashlib.sha256(s.encode("utf-8")).digest() for s in secrets if s)


def encrypt(plaintext: str | None) -> str | None:
    if not _CRYPTO_AVAILABLE:
        raise RuntimeError("未安装 cryptography，无法加密云存储凭据")
    if plaintext is None:
        return None
    keys = _keys()
    if not keys:
        raise ValueError("未配置 JWT_SECRET，无法加密凭据")
    aes = AESGCM(keys[0])
    nonce = os.urandom(_NONCE_LEN)
    ct = aes.encrypt(nonce, plaintext.encode("utf-8"), associated_data=None)
    return base64.b64encode(nonce + ct).decode("ascii")


def decrypt(token: str | None) -> str:
    if not token:
        return ""
    if not _CRYPTO_AVAILABLE:
        raise RuntimeError("未安装 cryptography，无法解密云存储凭据")
    raw = base64.b64decode(token.encode("ascii"))
    nonce, ct = raw[:_NONCE_LEN], raw[_NONCE_LEN:]
    last_exc: Exception | None = None
    for key in _keys():
        try:
            return AESGCM(key).decrypt(nonce, ct, associated_data=None).decode("utf-8")
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            continue
    if last_exc is not None:
        raise last_exc
    raise ValueError("未配置 JWT_SECRET，无法解密凭据")


def mask(value: str, head: int = 3, tail: int = 4) -> str:
    if not value:
        return ""
    if len(value) <= head + tail:
        return "•" * max(len(value), 6)
    return f"{value[:head]}{'•' * 4}{value[-tail:]}"
