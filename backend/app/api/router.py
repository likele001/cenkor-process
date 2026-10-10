# Copyright (C) 2026 CenkorProcess Project
# SPDX-License-Identifier: AGPL-3.0
from fastapi import APIRouter, Depends

from app.api.v1 import auth, batch, captcha, compliance, master, public_config, audit as audit_api, rbac, recipe, stock, storage as storage_api, notify_center, extensions as extensions_api, market as market_api
from app.core.deps import get_current_user, require_write_permission

api_router = APIRouter()

# 免登录公开路由：登录 / 验证码 / 公开品牌配置
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(captcha.router, prefix="/auth/captcha", tags=["auth-captcha"])
api_router.include_router(public_config.router, prefix="/public-config", tags=["public-config"])

# 业务路由：JWT Bearer 与 X-API-Key 双兼容；读仅需登录，写需对应域 manage 权限（A8）
_biz_deps = [Depends(get_current_user)]
api_router.include_router(master.router, prefix="/v1", tags=["master"], dependencies=[*_biz_deps, Depends(require_write_permission("master.manage"))])
api_router.include_router(recipe.router, prefix="/v1", tags=["recipe"], dependencies=[*_biz_deps, Depends(require_write_permission("recipe.manage"))])
api_router.include_router(batch.router, prefix="/v1", tags=["batch"], dependencies=[*_biz_deps, Depends(require_write_permission("batch.manage"))])
api_router.include_router(stock.router, prefix="/v1", tags=["stock"], dependencies=[*_biz_deps, Depends(require_write_permission("stock.manage"))])
api_router.include_router(compliance.router, prefix="/v1", tags=["compliance"], dependencies=[*_biz_deps, Depends(require_write_permission("compliance.manage"))])

# RBAC 管理（登录 + 细粒度 role.manage/user.manage 门控）
api_router.include_router(rbac.router, prefix="/v1", tags=["rbac"], dependencies=_biz_deps)

# 审计日志查询（登录 + 端点内 audit.view 门控）
api_router.include_router(audit_api.router, prefix="/v1", tags=["audit"], dependencies=_biz_deps)

# 附件存储 + 通知中心（登录即可；写/测试推送在端点内细粒度门控）
api_router.include_router(storage_api.router, prefix="/v1", tags=["storage"], dependencies=_biz_deps)
api_router.include_router(notify_center.router, prefix="/v1", tags=["notify"], dependencies=_biz_deps)

# WebSocket 实时推送（不走 HTTP 鉴权依赖；单独挂载）
from app.api.v1 import ws as ws_api  # noqa: E402
api_router.include_router(ws_api.router, tags=["ws"])

# 扩展宿主管理 API（登录 + 端点内 setting.manage 门控）
api_router.include_router(extensions_api.router, prefix="/v1/extensions", tags=["extensions"], dependencies=_biz_deps)

# 应用中心（market）：登录 + 端点内 market.view/market.manage 细粒度门控
api_router.include_router(market_api.router, prefix="/v1", tags=["market"], dependencies=_biz_deps)