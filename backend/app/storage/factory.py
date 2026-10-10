# Copyright (C) 2026 CenkorProcess Project
# SPDX-License-Identifier: AGPL-3.0
"""存储后端工厂：按配置解析具体 Storage 实现（A7，fork 自 CenkorMES 并精简）。

设计：
- 内置云驱动（aliyun/tencent/qiniu）惰性 import，避免未装 SDK 时导入期失败；
- 未注册/构造失败（缺 SDK、凭据不全）一律降级 local 并告警，绝不因配置未就绪导致上传中断；
- cenkor-process 暂未接平台级云凭据库，凭据从 settings 环境变量派生（STORAGE_<PROVIDER>_*）；
- register_driver 供测试/扩展注册零参自定义驱动。
"""
from __future__ import annotations

import importlib
import logging
import os
from typing import Any, Callable

from app.storage.base import Storage
from app.storage.local import LocalStorage

logger = logging.getLogger(__name__)

# 内置云驱动：provider -> (module, class)；惰性 import
_CLOUD_BUILDERS: dict[str, tuple[str, str]] = {
    "aliyun": ("app.storage.drivers.aliyun", "AliyunOSSStorage"),
    "tencent": ("app.storage.drivers.tencent", "TencentCOSStorage"),
    "qiniu": ("app.storage.drivers.qiniu", "QiniuStorage"),
}

_REGISTRY: dict[str, Callable[[], Storage]] = {}


def register_driver(name: str, factory: Callable[[], Storage]) -> None:
    _REGISTRY[name] = factory


def registered_drivers() -> list[str]:
    return sorted({"local", *_REGISTRY, *_CLOUD_BUILDERS})


def _resolve_driver_name(driver: str | None) -> str:
    from app.core.config import settings
    return (driver or getattr(settings, "STORAGE_DRIVER", "local") or "local").strip().lower()


def _load_creds(provider: str) -> dict:
    """从环境变量派生该 provider 的凭据（cenkor-process 暂未接云端凭据库/加密）。

    约定：STORAGE_<PROVIDER>_<FIELD>，如 STORAGE_ALIYUN_BUCKET / STORAGE_TENCENT_REGION。
    缺失即返回不完整 dict，交由驱动 _validate 抛错 → 上层降级 local。
    """
    prefix = f"STORAGE_{provider.upper()}_"
    fields = ("endpoint", "region", "bucket", "access_key", "secret_key", "custom_domain", "prefix")
    creds = {f: os.environ.get(f"{prefix}{f.upper()}", "") for f in fields}
    return creds


def _construct(name: str) -> Storage | None:
    if name == "local":
        return LocalStorage()
    if name in _REGISTRY:
        return _REGISTRY[name]()
    entry = _CLOUD_BUILDERS.get(name)
    if entry is None:
        return None
    module_path, class_name = entry
    module = importlib.import_module(module_path)
    cls = getattr(module, class_name)
    return cls(_load_creds(name))


def build_storage(driver: str | None = None, cfg: Any = None, db: Any = None) -> Storage:
    """按驱动名构造 Storage；未注册或构造失败时降级为 local（向后兼容）。"""
    name = _resolve_driver_name(driver)
    try:
        storage = _construct(name)
    except Exception as exc:  # noqa: BLE001 - 缺依赖/凭据不全等，降级本地保证可用
        logger.warning("构建存储驱动 %s 失败(%s)，降级为 local", name, exc)
        return LocalStorage()
    if storage is None:
        if name != "local":
            logger.warning("存储驱动 %s 未实现/未注册，降级为 local", name)
        return LocalStorage()
    return storage


def get_storage_backend(driver: str = "local") -> Storage:
    return build_storage(driver)


def get_active_storage(db: Any = None) -> Storage:
    """返回当前激活驱动（读 settings.STORAGE_DRIVER）。"""
    return build_storage(None)


def get_storage_for(driver: str, db: Any = None) -> Storage:
    return build_storage(driver)


def load_storage_config(db: Any = None) -> Any:
    from app.core.config import settings
    return type("Cfg", (), {"driver": settings.STORAGE_DRIVER})()
