# Copyright (C) 2026 CenkorProcess Project
# SPDX-License-Identifier: AGPL-3.0
"""配方缩放：目标批量 -> 各成分应投量。

公式（§4.3）：应投量 = 目标批量 × ratio_pct / 100 / (yield_pct / 100)
全 Decimal 运算，避免浮点误差。
"""
from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import BizError
from app.models.proc import Recipe, RecipeComponent


def scale_components(db: Session, recipe_id: int, target_qty: Decimal) -> dict:
    recipe = db.get(Recipe, recipe_id)
    if not recipe:
        raise BizError(404, "配方不存在")
    if target_qty <= 0:
        raise BizError(400, "目标批量必须大于 0")

    components = db.scalars(
        select(RecipeComponent)
        .where(RecipeComponent.recipe_id == recipe_id)
        .order_by(RecipeComponent.seq.asc(), RecipeComponent.id.asc())
    ).all()

    yield_factor = (recipe.yield_pct or Decimal("100")) / Decimal("100")
    if yield_factor <= 0:
        raise BizError(400, "收率必须大于 0")

    scaled = []
    for c in components:
        planned = (target_qty * (c.ratio_pct / Decimal("100")) / yield_factor).quantize(Decimal("0.0001"))
        scaled.append(
            {
                "component_id": c.id,
                "material_id": c.material_id,
                "uom_id": c.uom_id,
                "ratio_pct": c.ratio_pct,
                "tol_pct": c.tol_pct,
                "planned_qty": planned,
            }
        )

    return {
        "recipe_id": recipe.id,
        "target_qty": target_qty,
        "yield_pct": recipe.yield_pct,
        "components": scaled,
    }


def recipe_snapshot(db: Session, recipe: Recipe) -> dict:
    """生成批次级配方快照：发布后即不可变，在产批次不随配方改动而变（§3 闸4）。"""
    components = db.scalars(
        select(RecipeComponent)
        .where(RecipeComponent.recipe_id == recipe.id)
        .order_by(RecipeComponent.seq.asc(), RecipeComponent.id.asc())
    ).all()
    return {
        "recipe_id": recipe.id,
        "code": recipe.code,
        "version": recipe.version,
        "base_batch_qty": str(recipe.base_batch_qty),
        "base_uom_id": recipe.base_uom_id,
        "yield_pct": str(recipe.yield_pct),
        "components": [
            {
                "component_id": c.id,
                "material_id": c.material_id,
                "ratio_pct": str(c.ratio_pct),
                "uom_id": c.uom_id,
                "tol_pct": str(c.tol_pct),
                "is_key": c.is_key,
            }
            for c in components
        ],
    }