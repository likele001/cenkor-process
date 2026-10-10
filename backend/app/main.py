# Copyright (C) 2026 CenkorProcess Project
# SPDX-License-Identifier: AGPL-3.0
"""CenkorProcess 后端入口（P1 骨架）。

启动时：幂等种子（单位/仓库/物料/演示配方/演示批次库存）。

注意：schema 已交由 Alembic 版本化管理（`alembic upgrade head` 建表），默认不再
自动 `create_all`（见 settings.DB_AUTO_CREATE）。仅本地临时起库才手动开启。
"""
import logging
from datetime import datetime, timedelta
from decimal import Decimal

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.router import api_router
from app.core.config import settings
from app.core.db import SessionLocal, engine
from app.core.errors import BizError
from app.core.response import fail, ok
from app.core.security import ensure_secure_jwt_secret
from app.models import Base, User
from app.crud.rbac import create_default_roles
from app.crud.user import create_user, get_user_by_username
from app.models.proc import (
    Ccp,
    Material,
    Recipe,
    RecipeComponent,
    StockLot,
    Uom,
    Warehouse,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("cenkor-process")

app = FastAPI(title=settings.APP_NAME)

if settings.CORS_ORIGINS:
    _allowed = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_allowed,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(api_router, prefix="/api")

# 扩展宿主（A1）：api_router 挂载之后扫描 extensions/ 并热挂扩展路由（总开关关闭时跳过）
from app.extension_host import host as extension_host  # noqa: E402
extension_host.mount_all(app)


@app.get("/api/health")
def health():
    return ok({"status": "ok", "app": "cenkor-process", "port": settings.APP_PORT})


@app.exception_handler(HTTPException)
def http_exception_handler(_: Request, exc: HTTPException):
    return JSONResponse(status_code=200, content=fail(exc.status_code, str(exc.detail)))


@app.exception_handler(RequestValidationError)
def validation_exception_handler(_: Request, exc: RequestValidationError):
    return JSONResponse(status_code=200, content=fail(400, "参数校验失败", {"errors": exc.errors()}))


@app.exception_handler(BizError)
def biz_exception_handler(_: Request, exc: BizError):
    return JSONResponse(status_code=200, content=fail(exc.code, exc.msg))


@app.exception_handler(Exception)
def any_exception_handler(_: Request, exc: Exception):
    logger.error("未捕获异常: %s", exc, exc_info=exc)
    if settings.APP_ENV == "dev":
        return JSONResponse(status_code=200, content=fail(500, "服务器错误", {"error": str(exc), "type": type(exc).__name__}))
    return JSONResponse(status_code=200, content=fail(500, "服务器错误"))


def _seed(db: Session) -> None:
    if db.scalar(select(Uom.id).limit(1)):
        return

    uom = {
        "KG": Uom(code="KG", name="千克", is_base=True),
        "G": Uom(code="G", name="克", is_base=False),
        "L": Uom(code="L", name="升", is_base=True),
        "ML": Uom(code="ML", name="毫升", is_base=False),
        "PCS": Uom(code="PCS", name="件", is_base=True),
    }
    db.add_all(uom.values())
    db.flush()

    wh_rm = Warehouse(code="WH-RM", name="原料仓")
    wh_fg = Warehouse(code="WH-FG", name="成品仓")
    db.add_all([wh_rm, wh_fg])
    db.flush()

    m_sugar = Material(code="RM-SUGAR", name="白砂糖", base_uom_id=uom["KG"].id, shelf_life_days=365)
    m_water = Material(code="RM-WATER", name="纯水", base_uom_id=uom["L"].id, density_kg_l=Decimal("1.0"), shelf_life_days=30)
    m_drink = Material(code="FG-DRINK", name="成品饮料", base_uom_id=uom["L"].id, shelf_life_days=180)
    db.add_all([m_sugar, m_water, m_drink])
    db.flush()

    recipe = Recipe(
        code="RCP-DEMO",
        name="演示配方 · 含糖饮料",
        product_material_id=m_drink.id,
        version=1,
        status="released",
        base_batch_qty=Decimal("1000"),
        base_uom_id=uom["L"].id,
        yield_pct=Decimal("98"),
        note="P1 演示配方：白砂糖 8% + 纯水 92%，收率 98%",
    )
    db.add(recipe)
    db.flush()
    db.add_all(
        [
            RecipeComponent(recipe_id=recipe.id, material_id=m_sugar.id, seq=1, ratio_pct=Decimal("8"), uom_id=uom["KG"].id, tol_pct=Decimal("2"), is_key=True),
            RecipeComponent(recipe_id=recipe.id, material_id=m_water.id, seq=2, ratio_pct=Decimal("92"), uom_id=uom["L"].id, tol_pct=Decimal("1")),
        ]
    )

    now = datetime.now()
    db.add_all(
        [
            StockLot(warehouse_id=wh_rm.id, material_id=m_sugar.id, lot_no="SUGAR-2401", qty=Decimal("500"), uom_id=uom["KG"].id, produced_at=now - timedelta(days=300), expiry_at=now + timedelta(days=10), status="released", supplier_lot_no="S-2401"),
            StockLot(warehouse_id=wh_rm.id, material_id=m_sugar.id, lot_no="SUGAR-2402", qty=Decimal("800"), uom_id=uom["KG"].id, produced_at=now - timedelta(days=30), expiry_at=now + timedelta(days=60), status="released", supplier_lot_no="S-2402"),
            StockLot(warehouse_id=wh_rm.id, material_id=m_water.id, lot_no="WATER-2401", qty=Decimal("5000"), uom_id=uom["L"].id, produced_at=now, expiry_at=now + timedelta(days=30), status="released"),
        ]
    )
    db.commit()
    logger.info("已写入演示种子：单位/仓库/物料/配方/批次库存")


def _seed_compliance(db: Session) -> None:
    """P2 合规种子：演示 HACCP 关键控制点（幂等）。"""
    if db.scalar(select(Ccp.id).limit(1)):
        return
    db.add_all(
        [
            Ccp(
                code="CCP-01",
                name="杀菌温度",
                process_step="杀菌",
                param_key="temp_c",
                limit_min=Decimal("85"),
                limit_max=Decimal("95"),
                target_value=Decimal("90"),
                critical=True,
                monitor_freq="每批连续",
                corrective_action="立即升温至限值内并延长保温时间，重新取样复检；超限批次隔离待判。",
            ),
            Ccp(
                code="CCP-02",
                name="保温时长",
                process_step="杀菌",
                param_key="duration_min",
                limit_min=Decimal("15"),
                limit_max=None,
                target_value=Decimal("20"),
                critical=True,
                monitor_freq="每批",
                corrective_action="保温不足时返工重新杀菌，记录偏差并复检。",
            ),
        ]
    )
    db.commit()
    logger.info("已写入 P2 合规种子：HACCP 关键控制点 CCP-01/CCP-02")


def _seed_admin_user(db: Session) -> None:
    """对齐 CenkorMES 的管理员种子账号。首次启动创建 admin/admin123（幂等）。"""
    if get_user_by_username(db, "admin"):
        return
    try:
        create_user(db, "admin", "admin123", full_name="系统管理员", is_superuser=True)
        db.commit()
        logger.info("已创建默认管理员账号: admin")
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        logger.warning("管理员种子创建失败: %s", exc)


@app.on_event("startup")
def on_startup():
    ensure_secure_jwt_secret()
    # schema 由 Alembic 管理；DB_AUTO_CREATE 仅作为本地临时起库的开关，默认关闭
    if settings.DB_AUTO_CREATE:
        Base.metadata.create_all(bind=engine)
    if settings.DB_AUTO_SEED:
        db = SessionLocal()
        try:
            _seed(db)
            _seed_compliance(db)
            _seed_admin_user(db)
            create_default_roles(db)
            db.commit()
        except Exception as exc:  # noqa: BLE001
            db.rollback()
            logger.warning("种子写入失败: %s", exc)
        finally:
            db.close()
    # 扩展宿主启动：幂等迁移 + 扩展权限注入（失败开放，不阻断启动）
    try:
        extension_host.startup_host()
    except Exception as exc:  # noqa: BLE001
        logger.warning("扩展宿主启动失败: %s", exc)
    # 应用中心：启动授权到期门控线程（daemon，失败开放；幂等）
    try:
        from app.api.v1 import market
        market.start_entitlement_thread()
    except Exception as exc:  # noqa: BLE001
        logger.warning("应用中心授权门控线程启动失败: %s", exc)
