# Copyright (C) 2026 CenkorProcess Project
# SPDX-License-Identifier: AGPL-3.0
"""配方：创建（含成分）、发布、按目标批量缩放、改版。

字段级脱敏（A4）：recipe_components.ratio_pct / tol_pct 为敏感配方机密，
仅具备 `recipe.view_full` 权限者可见明文；否则后端序列化时置 None（前端拿不到明文）。
改版（revise）：生成新版本 + 强制 reason，变更由 A3 自动审计留痕（old/new ratio）。
"""
from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import get_current_permissions, get_current_user
from app.core.errors import BizError
from app.core.response import ok
from app.models.proc import Recipe, RecipeComponent
from app.models.user import User
from app.schemas.proc import (
    RecipeComponentOut,
    RecipeIn,
    RecipeOut,
    RecipeReviseIn,
    RecipeScaleOut,
)
from app.services import recipe_service
from app.services.audit import set_reason, soft_delete

router = APIRouter()

_VIEW_FULL = "recipe.view_full"


def _may_view_full(perms: list[str]) -> bool:
    return _VIEW_FULL in perms


def _mask_component(d: dict, allowed: bool) -> dict:
    """脱敏：无权限时抹掉 ratio_pct / tol_pct（后端裁剪，明文不出网）。"""
    if not allowed:
        d["ratio_pct"] = None
        d["tol_pct"] = None
    return d


@router.get("/recipes")
def list_recipes(db: Session = Depends(get_db)):
    rows = db.scalars(select(Recipe).where(Recipe.is_deleted.is_(False)).order_by(Recipe.id.desc())).all()
    return ok([RecipeOut.model_validate(r) for r in rows])


@router.post("/recipes")
def create_recipe(
    payload: RecipeIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    recipe = Recipe(
        code=payload.code,
        name=payload.name,
        product_material_id=payload.product_material_id,
        version=payload.version,
        recipe_type=payload.recipe_type,
        owner_id=getattr(user, "id", None),
        base_batch_qty=payload.base_batch_qty,
        base_uom_id=payload.base_uom_id,
        yield_pct=payload.yield_pct,
        note=payload.note,
        status="draft",
    )
    db.add(recipe)
    db.flush()
    for c in payload.components:
        db.add(RecipeComponent(recipe_id=recipe.id, **c.model_dump()))
    db.commit()
    db.refresh(recipe)
    return ok(RecipeOut.model_validate(recipe))


@router.get("/recipes/{recipe_id}")
def get_recipe(
    recipe_id: int,
    db: Session = Depends(get_db),
    perms: list[str] = Depends(get_current_permissions),
):
    recipe = db.get(Recipe, recipe_id)
    if not recipe or recipe.is_deleted:
        raise BizError(404, "配方不存在")
    components = db.scalars(
        select(RecipeComponent)
        .where(RecipeComponent.recipe_id == recipe_id)
        .order_by(RecipeComponent.seq.asc(), RecipeComponent.id.asc())
    ).all()
    allowed = _may_view_full(perms)
    data = RecipeOut.model_validate(recipe).model_dump()
    data["components"] = [
        _mask_component(RecipeComponentOut.model_validate(c).model_dump(), allowed) for c in components
    ]
    return ok(data)


@router.post("/recipes/{recipe_id}/release")
def release_recipe(recipe_id: int, db: Session = Depends(get_db)):
    recipe = db.get(Recipe, recipe_id)
    if not recipe:
        raise BizError(404, "配方不存在")
    recipe.status = "released"
    set_reason(db, "发布配方")
    db.commit()
    return ok({"id": recipe.id, "status": recipe.status})


@router.get("/recipes/{recipe_id}/scale")
def scale_recipe(
    recipe_id: int,
    qty: Decimal,
    db: Session = Depends(get_db),
    perms: list[str] = Depends(get_current_permissions),
):
    res = recipe_service.scale_components(db, recipe_id, qty)
    allowed = _may_view_full(perms)
    res["components"] = [_mask_component(c, allowed) for c in res["components"]]
    return ok(res)


@router.post("/recipes/{recipe_id}/revise")
def revise_recipe(
    recipe_id: int,
    payload: RecipeReviseIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """配方改版：基于旧版生成 version+1 的草稿新版；旧版置 obsolete。改版原因写入审计。"""
    old = db.get(Recipe, recipe_id)
    if not old or old.is_deleted:
        raise BizError(404, "配方不存在")
    if not payload.components:
        raise BizError(400, "改版必须提供成分配比")

    new_version = (db.scalar(
        select(Recipe.version)
        .where(Recipe.code == old.code, Recipe.is_deleted.is_(False))
        .order_by(Recipe.version.desc())
        .limit(1)
    ) or old.version) + 1

    set_reason(db, payload.reason)
    recipe = Recipe(
        code=old.code,
        name=payload.name or old.name,
        product_material_id=old.product_material_id,
        version=new_version,
        recipe_type=payload.recipe_type or old.recipe_type,
        owner_id=getattr(user, "id", None) or old.owner_id,
        base_batch_qty=payload.base_batch_qty or old.base_batch_qty,
        base_uom_id=payload.base_uom_id or old.base_uom_id,
        yield_pct=payload.yield_pct if payload.yield_pct is not None else old.yield_pct,
        note=payload.note if payload.note is not None else old.note,
        status="draft",
    )
    db.add(recipe)
    db.flush()
    for c in payload.components:
        db.add(RecipeComponent(recipe_id=recipe.id, **c.model_dump()))
    old.status = "obsolete"
    db.commit()
    db.refresh(recipe)
    return ok(RecipeOut.model_validate(recipe))


@router.delete("/recipes/{recipe_id}")
def delete_recipe(recipe_id: int, db: Session = Depends(get_db)):
    """逻辑删除配方（禁物理删除，保留历史与审计）。"""
    recipe = db.get(Recipe, recipe_id)
    if not recipe or recipe.is_deleted:
        raise BizError(404, "配方不存在")
    soft_delete(db, recipe, reason="删除配方")
    return ok({"id": recipe_id, "is_deleted": True})
