# Copyright (C) 2026 CenkorProcess Project
# SPDX-License-Identifier: AGPL-3.0
"""单位换算服务（对齐计划 §3 闸3：UoM 是「变 UoM」，非固定换算）。

规则：
  1) 同一单位 -> 原值；
  2) 显式换算表（uom_conversions）优先，支持物料专属与全局；
  3) 同量纲（质量/体积/数量）-> 走内置基单位系数（kg<->g、L<->mL …）；
  4) 跨量纲（质量<->体积）-> 必须给密度 kg/L（物料密度优先，其次换算表密度），
     因为 kg<->L 依赖密度、随物料与温度变化，不能当固定系数。
"""
from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import BizError
from app.models.proc import Material, Uom, UomConversion

QTY4 = Decimal("0.0001")

MASS, VOLUME, COUNT = "mass", "volume", "count"

_DIMENSION: dict[str, str] = {
    "KG": MASS, "G": MASS, "MG": MASS, "T": MASS,
    "L": VOLUME, "ML": VOLUME, "M3": VOLUME,
    "PCS": COUNT, "EA": COUNT, "BOX": COUNT, "PKG": COUNT,
}

# 换算到该量纲基单位（质量=KG，体积=L，数量=PCS）的系数
_TO_BASE: dict[str, Decimal] = {
    "KG": Decimal("1"), "G": Decimal("0.001"), "MG": Decimal("0.000001"), "T": Decimal("1000"),
    "L": Decimal("1"), "ML": Decimal("0.001"), "M3": Decimal("1000"),
    "PCS": Decimal("1"), "EA": Decimal("1"), "BOX": Decimal("1"), "PKG": Decimal("1"),
}

_BASE_CODE = {MASS: "KG", VOLUME: "L", COUNT: "PCS"}


def dimension_of(code: str) -> str | None:
    return _DIMENSION.get((code or "").upper())


def _find_conversion(db: Session, from_uom_id: int, to_uom_id: int, material_id: int | None) -> UomConversion | None:
    """先找物料专属换算，再退全局换算。"""
    if material_id is not None:
        row = db.scalar(
            select(UomConversion).where(
                UomConversion.from_uom_id == from_uom_id,
                UomConversion.to_uom_id == to_uom_id,
                UomConversion.material_id == material_id,
            )
        )
        if row:
            return row
    return db.scalar(
        select(UomConversion).where(
            UomConversion.from_uom_id == from_uom_id,
            UomConversion.to_uom_id == to_uom_id,
            UomConversion.material_id.is_(None),
        )
    )


def _resolve_density(db: Session, material_id: int | None, conv: UomConversion | None) -> Decimal | None:
    if material_id is not None:
        material = db.get(Material, material_id)
        if material and material.density_kg_l:
            return Decimal(material.density_kg_l)
    if conv is not None and conv.density_kg_l:
        return Decimal(conv.density_kg_l)
    return None


def convert(
    db: Session,
    qty: Decimal,
    from_uom_id: int,
    to_uom_id: int,
    material_id: int | None = None,
) -> dict:
    """把 qty 从 from_uom 换算为 to_uom，返回明细（含所用密度，便于追溯）。"""
    if qty is None:
        raise BizError(400, "数量不能为空")

    if from_uom_id == to_uom_id:
        return {"result": qty, "mode": "identity", "density_kg_l": None}

    from_uom = db.get(Uom, from_uom_id)
    to_uom = db.get(Uom, to_uom_id)
    if not from_uom or not to_uom:
        raise BizError(404, "单位不存在")

    conv = _find_conversion(db, from_uom_id, to_uom_id, material_id)
    if conv is not None and conv.factor is not None:
        return {"result": (qty * Decimal(conv.factor)).quantize(QTY4), "mode": "factor", "density_kg_l": None}

    dim_from = dimension_of(from_uom.code)
    dim_to = dimension_of(to_uom.code)
    if dim_from is None or dim_to is None:
        raise BizError(400, f"单位 {from_uom.code}->{to_uom.code} 未内置量纲，请在换算表中显式配置 factor")

    if dim_from == dim_to:
        base_qty = qty * _TO_BASE[from_uom.code]
        result = base_qty / _TO_BASE[to_uom.code]
        return {"result": result.quantize(QTY4), "mode": "same_dimension", "density_kg_l": None}

    if {dim_from, dim_to} == {MASS, VOLUME}:
        density = _resolve_density(db, material_id, conv)
        if not density or density <= 0:
            raise BizError(400, "质量<->体积换算需要物料密度 density_kg_l（或换算表密度）")
        base_qty = qty * _TO_BASE[from_uom.code]  # -> KG 或 L
        base_qty = base_qty / density if dim_from == MASS else base_qty * density
        result = base_qty / _TO_BASE[to_uom.code]
        return {"result": result.quantize(QTY4), "mode": "density", "density_kg_l": density}

    raise BizError(400, f"不支持 {from_uom.code} -> {to_uom.code} 的换算")