# Copyright (C) 2026 CenkorProcess Project
# SPDX-License-Identifier: AGPL-3.0
"""扩展宿主管理 API（A1）：列表 / 重扫热挂卸 / 本地启停 / 卸载 / 前端插件。

读接口登录即可；写操作（rescan/enable/disable/unload）需 `setting.manage`。
所有装卸均运行期即时生效，无需重启服务。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse

from app.core.deps import require_permissions
from app.core.response import ok
from app.extension_host import host as ext_host
from app.extension_host.loader import rescan_extensions, run_extension_migrations
from app.extension_host.state import runtime

router = APIRouter()

_MANAGE = Depends(require_permissions(["setting.manage"]))


@router.get("")
def list_extensions():
    """已安装扩展及启用状态（前端加载器据此决定加载哪些插件、渲染哪些菜单）。"""
    return ok({"items": runtime.status_list(), "synced_at": runtime.synced_at})


@router.post("/rescan", dependencies=[_MANAGE])
def rescan(request: Request):
    """重新扫描扩展目录：新装热挂、移除热卸，并补跑迁移与权限注入。"""
    if not runtime.installed and runtime.extensions_dir is None:
        # 首次扫描（宿主未初始化时兜底）
        base = ext_host.extensions_base_dir()
        base.mkdir(parents=True, exist_ok=True)
        runtime.extensions_dir = base
    result = rescan_extensions(request.app)
    run_extension_migrations(ext_host.extensions_base_dir())
    ext_host._sync_permissions()
    return ok(result)


@router.post("/{key}/enable", dependencies=[_MANAGE])
def enable_extension(request: Request, key: str):
    """启用扩展：清除本地禁用覆盖 + 运行期热挂载路由。"""
    if key not in runtime.installed:
        raise HTTPException(status_code=404, detail="扩展不存在")
    runtime.set_override(key, None)
    ext_host.hot_setup_extension(request.app, key)
    return ok({"key": key, "enabled": runtime.is_enabled(key)})


@router.post("/{key}/disable", dependencies=[_MANAGE])
def disable_extension(request: Request, key: str):
    """停用扩展：置本地禁用覆盖；已挂载路由经 require_extension 门控即时返回 403。"""
    if key not in runtime.installed:
        raise HTTPException(status_code=404, detail="扩展不存在")
    runtime.set_override(key, "disabled")
    return ok({"key": key, "enabled": runtime.is_enabled(key)})


@router.delete("/{key}", dependencies=[_MANAGE])
def unload_extension(request: Request, key: str):
    """运行期卸载扩展路由（仅摘路由，不删除磁盘文件；重启后按目录状态重载）。"""
    removed = ext_host.hot_teardown_extension(request.app, key)
    runtime.installed.pop(key, None)
    return ok({"key": key, "routes_removed": removed})


@router.get("/{key}/plugin.js")
def get_plugin_js(key: str):
    """返回扩展前端插件脚本（仅启用状态可获取）。"""
    info = runtime.installed.get(key)
    if not info:
        raise HTTPException(status_code=404, detail="扩展不存在")
    if not runtime.is_enabled(key):
        raise HTTPException(status_code=403, detail="扩展未启用")
    file = info["path"] / "frontend" / "plugin.js"
    if not file.is_file():
        raise HTTPException(status_code=404, detail="该扩展没有前端插件")
    return FileResponse(str(file), media_type="application/javascript")
