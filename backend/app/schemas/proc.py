# Copyright (C) 2026 CenkorProcess Project
# SPDX-License-Identifier: AGPL-3.0
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------- master ----------
class UomIn(BaseModel):
    code: str
    name: str
    is_base: bool = False


class UomOut(ORMModel):
    id: int
    code: str
    name: str
    is_base: bool


class WarehouseIn(BaseModel):
    code: str
    name: str


class WarehouseOut(ORMModel):
    id: int
    code: str
    name: str
    is_active: bool


class MaterialIn(BaseModel):
    code: str
    name: str
    base_uom_id: int
    density_kg_l: Decimal | None = None
    shelf_life_days: int | None = None
    storage_condition: str | None = None
    quality_std: str | None = None


class MaterialOut(ORMModel):
    id: int
    code: str
    name: str
    base_uom_id: int
    density_kg_l: Decimal | None
    shelf_life_days: int | None
    storage_condition: str | None
    quality_std: str | None
    is_active: bool


class MaterialUpdate(BaseModel):
    name: str | None = None
    base_uom_id: int | None = None
    density_kg_l: Decimal | None = None
    shelf_life_days: int | None = None
    storage_condition: str | None = None
    quality_std: str | None = None
    is_active: bool | None = None


class UomConversionIn(BaseModel):
    from_uom_id: int
    to_uom_id: int
    material_id: int | None = None
    factor: Decimal | None = None
    density_kg_l: Decimal | None = None
    note: str | None = None


# ---------- recipe ----------
class RecipeComponentIn(BaseModel):
    material_id: int
    ratio_pct: Decimal
    uom_id: int
    seq: int = 1
    tol_pct: Decimal = Decimal("0")
    is_key: bool = False
    note: str | None = None


class RecipeIn(BaseModel):
    code: str
    name: str
    product_material_id: int
    version: int = 1
    recipe_type: str = "production"
    base_batch_qty: Decimal
    base_uom_id: int
    yield_pct: Decimal = Decimal("100")
    note: str | None = None
    components: list[RecipeComponentIn] = Field(default_factory=list)


class RecipeOut(ORMModel):
    id: int
    code: str
    name: str
    product_material_id: int
    version: int
    status: str
    recipe_type: str
    owner_id: int | None
    base_batch_qty: Decimal
    base_uom_id: int
    yield_pct: Decimal
    note: str | None
    created_at: datetime


class RecipeComponentOut(ORMModel):
    id: int
    recipe_id: int
    material_id: int
    seq: int
    ratio_pct: Decimal | None
    uom_id: int
    tol_pct: Decimal | None
    is_key: bool


class ScaledComponent(BaseModel):
    component_id: int
    material_id: int
    uom_id: int
    ratio_pct: Decimal | None
    tol_pct: Decimal | None
    planned_qty: Decimal


class RecipeScaleOut(BaseModel):
    recipe_id: int
    target_qty: Decimal
    yield_pct: Decimal
    components: list[ScaledComponent]


class RecipeReviseIn(BaseModel):
    """配方改版：生成新版本（草稿），改版原因必填并写入审计。"""
    reason: str = Field(min_length=1, description="改版原因（必填，写入审计）")
    name: str | None = None
    recipe_type: str | None = None
    base_batch_qty: Decimal | None = None
    base_uom_id: int | None = None
    yield_pct: Decimal | None = None
    note: str | None = None
    components: list[RecipeComponentIn] = Field(default_factory=list)


# ---------- batch ----------
class BatchIn(BaseModel):
    recipe_id: int
    planned_qty: Decimal
    uom_id: int | None = None
    planned_date: date | None = None
    note: str | None = None


class BatchOut(ORMModel):
    id: int
    batch_no: str
    recipe_id: int
    recipe_version: int
    product_material_id: int
    planned_qty: Decimal
    uom_id: int
    planned_date: date | None
    status: str
    produced_qty: Decimal | None
    scrap_qty: Decimal
    yield_pct: Decimal | None
    created_at: datetime
    completed_at: datetime | None


class DispenseIn(BaseModel):
    component_id: int | None = None
    material_id: int
    planned_qty: Decimal
    actual_qty: Decimal
    uom_id: int
    tol_pct: Decimal = Decimal("0")
    lot_id: int | None = None
    operator_id: int | None = None


class ByproductIn(BaseModel):
    material_id: int
    qty: Decimal
    uom_id: int
    warehouse_id: int | None = None
    status: str = "received"


class BatchCompleteIn(BaseModel):
    dispenses: list[DispenseIn] = Field(default_factory=list)
    produced_qty: Decimal
    byproduct: list[ByproductIn] = Field(default_factory=list)
    warehouse_id: int | None = None
    auto_issue: bool = True
    allow_deviation: bool = False
    allow_unplanned: bool = False


class BatchCompleteOut(BaseModel):
    batch_id: int
    batch_no: str
    status: str
    produced_lot_id: int
    produced_lot_no: str
    consumed: list[dict]
    deviations: list[dict]


# ---------- stock ----------
class LotReceiptIn(BaseModel):
    warehouse_id: int
    material_id: int
    lot_no: str
    qty: Decimal
    uom_id: int
    produced_at: datetime | None = None
    expiry_at: datetime | None = None
    status: str = "released"
    supplier_lot_no: str | None = None


class StockLotOut(ORMModel):
    id: int
    warehouse_id: int
    material_id: int
    lot_no: str
    qty: Decimal
    uom_id: int
    produced_at: datetime | None
    expiry_at: datetime | None
    status: str
    source_batch_id: int | None
    # 以下为只读计算字段（A5 临期预警）；由服务/端点回填，不映射 ORM 列
    days_to_expiry: int | None = None
    expired: bool = False
    near_expiry: bool = False


class FefoPlanItem(BaseModel):
    lot_id: int
    lot_no: str
    expiry_at: datetime | None
    take_qty: Decimal


class FefoPlanOut(BaseModel):
    warehouse_id: int
    material_id: int
    need_qty: Decimal
    enough: bool
    plan: list[FefoPlanItem]


class GenealogyNode(BaseModel):
    lot_id: int
    lot_no: str
    op_type: str
    amount: Decimal


# ---------- 批次发布 / 应投清单（§3 闸4） ----------
class BatchReleaseOut(BaseModel):
    id: int
    batch_no: str
    status: str
    recipe_version: int
    has_snapshot: bool


class DispensePlanLine(BaseModel):
    component_id: int | None
    material_id: int
    uom_id: int
    ratio_pct: Decimal | None
    tol_pct: Decimal | None
    planned_qty: Decimal
    is_key: bool


class DispensePlanOut(BaseModel):
    batch_id: int
    batch_no: str
    recipe_id: int | None
    recipe_version: int | None
    planned_qty: Decimal
    yield_pct: Decimal
    lines: list[DispensePlanLine]


# ---------- 单位换算（§3 闸3） ----------
class UomConvertOut(BaseModel):
    from_uom_id: int
    to_uom_id: int
    material_id: int | None
    qty: Decimal
    result: Decimal
    mode: str
    density_kg_l: Decimal | None


# ---------- 合批 / 拆批（§3 闸2） ----------
class LotMergeIn(BaseModel):
    lot_ids: list[int]
    lot_no: str | None = None
    status: str = "released"


class LotSplitPart(BaseModel):
    qty: Decimal
    lot_no: str | None = None
    expiry_at: datetime | None = None


class LotSplitIn(BaseModel):
    parts: list[LotSplitPart]
    status: str | None = None


# ---------- P2 合规与质量 ----------
# ---- HACCP / CCP ----
class CcpIn(BaseModel):
    code: str
    name: str
    process_step: str | None = None
    param_key: str = "temp_c"
    uom_id: int | None = None
    limit_min: Decimal | None = None
    limit_max: Decimal | None = None
    target_value: Decimal | None = None
    critical: bool = True
    monitor_freq: str | None = None
    corrective_action: str | None = None


class CcpOut(ORMModel):
    id: int
    code: str
    name: str
    process_step: str | None
    param_key: str
    uom_id: int | None
    limit_min: Decimal | None
    limit_max: Decimal | None
    target_value: Decimal | None
    critical: bool
    monitor_freq: str | None
    corrective_action: str | None
    is_active: bool


class CcpRecordIn(BaseModel):
    ccp_id: int
    batch_id: int | None = None
    operation_id: int | None = None
    lot_id: int | None = None
    measured_value: Decimal
    uom_id: int | None = None
    measured_at: datetime | None = None
    operator_id: int | None = None
    deviation_note: str | None = None
    corrective_action: str | None = None


class CcpRecordOut(ORMModel):
    id: int
    ccp_id: int
    batch_id: int | None
    operation_id: int | None
    lot_id: int | None
    measured_value: Decimal
    uom_id: int | None
    measured_at: datetime
    operator_id: int | None
    status: str
    deviation_note: str | None
    corrective_action: str | None
    verified_by: int | None
    verified_at: datetime | None


# ---- CIP 清洗 ----
class CipLogIn(BaseModel):
    station: str
    batch_id: int | None = None
    cip_type: str = "tank"
    start_at: datetime
    end_at: datetime | None = None
    duration_min: int | None = None
    caustic_conc_pct: Decimal | None = None
    caustic_temp_c: Decimal | None = None
    acid_conc_pct: Decimal | None = None
    acid_temp_c: Decimal | None = None
    rinse_conductivity: Decimal | None = None
    final_rinse_ph: Decimal | None = None
    operator_id: int | None = None
    note: str | None = None


class CipLogOut(ORMModel):
    id: int
    station: str
    batch_id: int | None
    cip_type: str
    start_at: datetime
    end_at: datetime | None
    duration_min: int | None
    caustic_conc_pct: Decimal | None
    caustic_temp_c: Decimal | None
    acid_conc_pct: Decimal | None
    acid_temp_c: Decimal | None
    rinse_conductivity: Decimal | None
    final_rinse_ph: Decimal | None
    result: str
    operator_id: int | None
    note: str | None


# ---- CoA 检验 / 放行 ----
class CoaIn(BaseModel):
    material_id: int
    coa_no: str | None = None
    lot_id: int | None = None
    batch_id: int | None = None
    direction: str = "incoming"
    sample_at: datetime | None = None
    tested_at: datetime | None = None
    tester_id: int | None = None
    items: list[dict] = Field(default_factory=list)
    note: str | None = None


class CoaOut(ORMModel):
    id: int
    coa_no: str
    lot_id: int | None
    material_id: int
    batch_id: int | None
    direction: str
    sample_at: datetime | None
    tested_at: datetime | None
    tester_id: int | None
    result: str
    items: list | None
    released_by: int | None
    released_at: datetime | None
    locked: bool
    note: str | None
    created_at: datetime


class CoaDecideIn(BaseModel):
    result: str = Field(description="pass / fail / hold")
    released_by: int | None = None
    note: str | None = None


# ---- 杀菌时间-温度记录 ----
class TempLogIn(BaseModel):
    temp_c: Decimal
    batch_id: int | None = None
    operation_id: int | None = None
    ccp_id: int | None = None
    station: str | None = None
    stage: str = "hold"
    recorded_at: datetime | None = None
    duration_min: int | None = None
    note: str | None = None


class TempLogOut(ORMModel):
    id: int
    batch_id: int | None
    operation_id: int | None
    ccp_id: int | None
    station: str | None
    stage: str
    recorded_at: datetime
    temp_c: Decimal
    duration_min: int | None
    in_range: bool
    note: str | None


class TempLogCreateOut(BaseModel):
    log: TempLogOut
    in_range: bool
    alert_raised: bool


class ComplianceAlertOut(BaseModel):
    ccp_deviations: list[dict]
    temp_out_of_range: list[dict]
    cip_failed: list[dict]
    coa_failed: list[dict]
    total: int