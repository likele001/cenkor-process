# Copyright (C) 2026 CenkorProcess Project
# SPDX-License-Identifier: AGPL-3.0
"""主数据：单位 / 单位换算 / 物料 / 仓库。

P1 自带最小主数据以便独立跑通闭环；fork 完成后可切换为平台主数据（materials/suppliers）。
"""
from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.errors import BizError
from app.core.response import ok
from app.models.proc import Material, Uom, UomConversion, Warehouse
from app.schemas.proc import MaterialIn, MaterialOut, MaterialUpdate, UomIn, UomOut, WarehouseIn, WarehouseOut
from app.services import uom_service
from app.services.audit import soft_delete

router = APIRouter()


@router.get("/uoms")
def list_uoms(db: Session = Depends(get_db)):
    rows = db.scalars(select(Uom).order_by(Uom.id.asc())).all()
    return ok([UomOut.model_validate(r) for r in rows])


@router.post("/uoms")
def create_uom(payload: UomIn, db: Session = Depends(get_db)):
    uom = Uom(**payload.model_dump())
    db.add(uom)
    db.commit()
    db.refresh(uom)
    return ok(UomOut.model_validate(uom))


@router.get("/materials")
def list_materials(db: Session = Depends(get_db)):
    rows = db.scalars(select(Material).where(Material.is_deleted.is_(False)).order_by(Material.id.asc())).all()
    return ok([MaterialOut.model_validate(r) for r in rows])


@router.post("/materials")
def create_material(payload: MaterialIn, db: Session = Depends(get_db)):
    material = Material(**payload.model_dump())
    db.add(material)
    db.commit()
    db.refresh(material)
    return ok(MaterialOut.model_validate(material))


@router.put("/materials/{material_id}")
def update_material(material_id: int, payload: MaterialUpdate, db: Session = Depends(get_db)):
    """维护物料主数据（含存储条件/质量标准等字段）。"""
    material = db.get(Material, material_id)
    if not material or material.is_deleted:
        raise BizError(404, "物料不存在")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(material, key, value)
    db.commit()
    db.refresh(material)
    return ok(MaterialOut.model_validate(material))


@router.get("/warehouses")
def list_warehouses(db: Session = Depends(get_db)):
    rows = db.scalars(select(Warehouse).where(Warehouse.is_deleted.is_(False)).order_by(Warehouse.id.asc())).all()
    return ok([WarehouseOut.model_validate(r) for r in rows])


@router.post("/warehouses")
def create_warehouse(payload: WarehouseIn, db: Session = Depends(get_db)):
    wh = Warehouse(**payload.model_dump())
    db.add(wh)
    db.commit()
    db.refresh(wh)
    return ok(WarehouseOut.model_validate(wh))


@router.post("/uom-conversions")
def create_conversion(payload: dict, db: Session = Depends(get_db)):
    conv = UomConversion(**payload)
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return ok({"id": conv.id})


@router.get("/uom/convert")
def uom_convert(
    qty: Decimal,
    from_uom_id: int,
    to_uom_id: int,
    material_id: int | None = None,
    db: Session = Depends(get_db),
):
    """单位换算：同量纲走系数，质量<->体积走物料密度（§3 闸3）。"""
    res = uom_service.convert(db, qty, from_uom_id, to_uom_id, material_id)
    return ok({"from_uom_id": from_uom_id, "to_uom_id": to_uom_id, "material_id": material_id, "qty": qty, **res})


@router.delete("/materials/{material_id}")
def delete_material(material_id: int, db: Session = Depends(get_db)):
    """逻辑删除物料（禁物理删除，保留追溯）。"""
    obj = db.get(Material, material_id)
    if not obj or obj.is_deleted:
        raise BizError(404, "物料不存在")
    soft_delete(db, obj, reason="删除物料")
    return ok({"id": material_id, "is_deleted": True})


@router.delete("/warehouses/{warehouse_id}")
def delete_warehouse(warehouse_id: int, db: Session = Depends(get_db)):
    obj = db.get(Warehouse, warehouse_id)
    if not obj or obj.is_deleted:
        raise BizError(404, "仓库不存在")
    soft_delete(db, obj, reason="删除仓库")
    return ok({"id": warehouse_id, "is_deleted": True})