# Copyright (C) 2026 CenkorProcess Project
# SPDX-License-Identifier: AGPL-3.0
"""扩展宿主 facade：供 ``app/main.py`` 与运行期装卸调用的统一入口。"""
from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import SessionLocal

from .loader import mount_extensions, run_extension_migrations
from .state import runtime

logger = logging.getLogger("uvicorn.error")


def hot_setup_extension(app, key: str) -> None:
    """安装/更新后运行期即时生效：执行迁移 + 注入权限 + 热挂载路由（无需重启）。"""
    from .loader import mount_extension_router

    info = runtime.installed.get(key)
    if not info:
        return
    run_extension_migrations(extensions_base_dir())
    _sync_permissions()
    try:
        mount_extension_router(app, key, Path(info["path"]))
    except Exception as e:  # noqa: BLE001 - 热挂载失败不阻塞安装结果（重启仍可生效）
        logger.error("[extension] 运行期热挂载 %s 失败: %s", key, e)


def hot_teardown_extension(app, key: str) -> int:
    """卸载后运行期即时移除路由（无需重启）。返回移除路由数。"""
    from .loader import unmount_extension_router

    removed = unmount_extension_router(app, key)
    if removed:
        logger.info("[extension] 运行期移除扩展路由 %d 条: %s", removed, key)
    return removed


def extensions_base_dir() -> Path:
    """解析扩展目录（相对路径按 backend/ 解析）。"""
    raw = (settings.EXTENSIONS_DIR or "./extensions").strip()
    path = Path(raw)
    if not path.is_absolute():
        path = Path(__file__).resolve().parents[2] / raw
    return path.resolve()


def mount_all(app) -> None:
    """模块导入期调用：扫描扩展并挂载路由（总开关关闭时跳过）。"""
    if not settings.EXTENSIONS_ENABLED:
        logger.info("[extension] 扩展宿主已关闭（EXTENSIONS_ENABLED=0）")
        return
    base = extensions_base_dir()
    base.mkdir(parents=True, exist_ok=True)
    mount_extensions(app, base)
    if runtime.installed:
        logger.info("[extension] 已发现 %d 个扩展: %s", len(runtime.installed), ", ".join(sorted(runtime.installed)))


def startup_host() -> None:
    """on_startup 调用：迁移 + 权限注入。

    授权快照/心跳（对接独立应用中心）属于商业化阶段（B），此处默认失败开放（本地放行）。
    """
    if not settings.EXTENSIONS_ENABLED:
        return
    run_extension_migrations(extensions_base_dir())
    _sync_permissions()


def _sync_permissions() -> None:
    """把已启用扩展声明的权限点写入 DB，并补授 admin 角色。"""
    from app.models.permission import Permission
    from app.models.role import Role

    wanted: dict[str, str] = {}
    for key, info in runtime.installed.items():
        if not runtime.is_enabled(key):
            continue
        for p in info["manifest"].permissions:
            code = str(p.get("code") or "").strip()
            if code:
                wanted[code] = str(p.get("name") or code)
    if not wanted:
        return

    db: Session = SessionLocal()
    try:
        existing = {p.code: p for p in db.scalars(select(Permission)).all()}
        created: list[Permission] = []
        for code, name in wanted.items():
            if code not in existing:
                perm = Permission(code=code, name=name)
                db.add(perm)
                existing[code] = perm
                created.append(perm)
        db.flush()
        admin = db.scalar(select(Role).where(Role.code == "admin"))
        if admin:
            admin_codes = {p.code for p in (admin.permissions or [])}
            missing = [existing[c] for c in wanted if c not in admin_codes]
            if missing:
                admin.permissions.extend(missing)
                logger.info("[extension] 补授扩展权限点到 admin %d 个", len(missing))
        if created:
            logger.info("[extension] 注入扩展权限点 %d 个: %s", len(created), ", ".join(p.code for p in created))
        db.commit()
    except Exception as e:  # noqa: BLE001 - 权限注入失败不阻塞启动
        db.rollback()
        logger.error("[extension] 同步扩展权限失败: %s", e)
    finally:
        db.close()
