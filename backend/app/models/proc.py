# Copyright (C) 2026 CenkorProcess Project
# SPDX-License-Identifier: AGPL-3.0
"""流程制造领域模型（P1 骨架）。

命名规范：独立产品库，领域表直接用业务名（recipes/batches/stock_lots/...），不加命名空间前缀。
两条硬约束：
  1) 数量一律 DECIMAL(18,4)，不使用整数（对齐 §8）；
  2) kg<->L 走「物料密度」分支，不进固定 factor（对齐 §3 闸3）。
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.mixins import SoftDeleteMixin

QTY = Numeric(18, 4)
RATE = Numeric(18, 8)


class Warehouse(SoftDeleteMixin, Base):
    __tablename__ = "warehouses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(32), nullable=False, unique=True, comment="仓库编码")
    name: Mapped[str] = mapped_column(String(64), nullable=False, comment="仓库名称")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())


class Uom(Base):
    __tablename__ = "uoms"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(16), nullable=False, unique=True, comment="单位编码 kg/L/pcs")
    name: Mapped[str] = mapped_column(String(32), nullable=False)
    is_base: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0", comment="是否基单位")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())


class UomConversion(Base):
    """单位换算。material_id 非空 = 物料专属换算（如按密度 kg<->L）；为空 = 全局固定换算。"""

    __tablename__ = "uom_conversions"
    __table_args__ = (
        UniqueConstraint("from_uom_id", "to_uom_id", "material_id", name="uq_uom_conv"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    from_uom_id: Mapped[int] = mapped_column(ForeignKey("uoms.id"), nullable=False)
    to_uom_id: Mapped[int] = mapped_column(ForeignKey("uoms.id"), nullable=False)
    material_id: Mapped[int | None] = mapped_column(ForeignKey("materials.id"), nullable=True)
    factor: Mapped[Decimal | None] = mapped_column(RATE, nullable=True, comment="固定换算系数；密度换算时为空")
    density_kg_l: Mapped[Decimal | None] = mapped_column(RATE, nullable=True, comment="密度 kg/L；仅体积<->质量换算用")
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())


class Material(SoftDeleteMixin, Base):
    __tablename__ = "materials"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    base_uom_id: Mapped[int] = mapped_column(ForeignKey("uoms.id"), nullable=False, comment="基单位")
    density_kg_l: Mapped[Decimal | None] = mapped_column(RATE, nullable=True, comment="密度 kg/L，体积<->质量换算")
    shelf_life_days: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="保质期天数，用于推算 expiry_at")
    storage_condition: Mapped[str | None] = mapped_column(String(64), nullable=True, comment="存储条件，如常温/冷藏/避光")
    quality_std: Mapped[str | None] = mapped_column(Text, nullable=True, comment="质量标准/验收指标（文本或 JSON 描述）")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())


class Recipe(SoftDeleteMixin, Base):
    """配方（配比可缩放）。发布后版本只读；在制批次用 recipe_snapshot 锁定。"""

    __tablename__ = "recipes"
    __table_args__ = (UniqueConstraint("code", "version", name="uq_recipe_code_ver"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    product_material_id: Mapped[int] = mapped_column(ForeignKey("materials.id"), nullable=False, comment="产出物料")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft", server_default="draft", comment="draft/released/obsolete")
    recipe_type: Mapped[str] = mapped_column(String(16), nullable=False, default="production", server_default="production", index=True, comment="配方类型：production 量产 / trial 试制")
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, comment="配方负责人")
    base_batch_qty: Mapped[Decimal] = mapped_column(QTY, nullable=False, comment="基准批量")
    base_uom_id: Mapped[int] = mapped_column(ForeignKey("uoms.id"), nullable=False)
    yield_pct: Mapped[Decimal] = mapped_column(RATE, nullable=False, default=Decimal("100"), server_default="100", comment="收率 %")
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())


class RecipeComponent(Base):
    """配方成分：ratio_pct 为占成品比例（%），按目标批量线性缩放。"""

    __tablename__ = "recipe_components"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    recipe_id: Mapped[int] = mapped_column(ForeignKey("recipes.id"), nullable=False, index=True)
    material_id: Mapped[int] = mapped_column(ForeignKey("materials.id"), nullable=False)
    seq: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    ratio_pct: Mapped[Decimal] = mapped_column(RATE, nullable=False, comment="占成品比例 %")
    uom_id: Mapped[int] = mapped_column(ForeignKey("uoms.id"), nullable=False)
    tol_pct: Mapped[Decimal] = mapped_column(RATE, nullable=False, default=Decimal("0"), server_default="0", comment="称重容差 %")
    is_key: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0", comment="是否关键料")
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)


class Batch(SoftDeleteMixin, Base):
    """批次：流程制造的一等生产对象（对应离散的 work_orders）。"""

    __tablename__ = "batches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    batch_no: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    recipe_id: Mapped[int] = mapped_column(ForeignKey("recipes.id"), nullable=False)
    recipe_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    recipe_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True, comment="批次级配方快照（不可变）")
    product_material_id: Mapped[int] = mapped_column(ForeignKey("materials.id"), nullable=False)
    planned_qty: Mapped[Decimal] = mapped_column(QTY, nullable=False)
    uom_id: Mapped[int] = mapped_column(ForeignKey("uoms.id"), nullable=False)
    planned_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="planned", server_default="planned", comment="planned/released/in_progress/completed/closed/hold")
    produced_qty: Mapped[Decimal | None] = mapped_column(QTY, nullable=True)
    scrap_qty: Mapped[Decimal] = mapped_column(QTY, nullable=False, default=Decimal("0"), server_default="0")
    yield_pct: Mapped[Decimal | None] = mapped_column(RATE, nullable=True, comment="实际收率 %")
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class BatchOperation(Base):
    """批次工序：配料/混合/杀菌/灌装/CIP 等，携带时间-温度参数。"""

    __tablename__ = "batch_operations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("batches.id"), nullable=False, index=True)
    seq: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    op_type: Mapped[str] = mapped_column(String(20), nullable=False, default="mix", server_default="mix", comment="dispense/mix/heat/fill/cip/pack")
    planned_qty: Mapped[Decimal | None] = mapped_column(QTY, nullable=True)
    actual_qty: Mapped[Decimal | None] = mapped_column(QTY, nullable=True)
    uom_id: Mapped[int | None] = mapped_column(ForeignKey("uoms.id"), nullable=True)
    temp_c: Mapped[Decimal | None] = mapped_column(Numeric(9, 2), nullable=True, comment="温度 ℃")
    duration_min: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="时长 分钟")
    params: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", server_default="pending", comment="pending/running/done/skipped")
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class StockLot(SoftDeleteMixin, Base):
    """批次库存（对应离散的 stocks，但批次是一等公民）。数量为小数，含效期以支持 FEFO。"""

    __tablename__ = "stock_lots"
    __table_args__ = (
        UniqueConstraint("warehouse_id", "material_id", "lot_no", name="uq_stock_lot"),
        Index("ix_stock_lots_fefo", "warehouse_id", "material_id", "status", "expiry_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    warehouse_id: Mapped[int] = mapped_column(ForeignKey("warehouses.id"), nullable=False)
    material_id: Mapped[int] = mapped_column(ForeignKey("materials.id"), nullable=False)
    lot_no: Mapped[str] = mapped_column(String(48), nullable=False)
    qty: Mapped[Decimal] = mapped_column(QTY, nullable=False, default=Decimal("0"), server_default="0")
    uom_id: Mapped[int] = mapped_column(ForeignKey("uoms.id"), nullable=False)
    produced_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    expiry_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="效期，FEFO 排序键")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="received", server_default="received", comment="received/released/quarantined/rejected/consumed")
    source_batch_id: Mapped[int | None] = mapped_column(ForeignKey("batches.id"), nullable=True, comment="产出该批的批次")
    supplier_lot_no: Mapped[str | None] = mapped_column(String(48), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())


class LotGenealogy(Base):
    """批次谱系：parent_lot -> child_lot，支持 consume/merge/split/produce。"""

    __tablename__ = "lot_genealogy"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    parent_lot_id: Mapped[int] = mapped_column(ForeignKey("stock_lots.id"), nullable=False, index=True)
    child_lot_id: Mapped[int] = mapped_column(ForeignKey("stock_lots.id"), nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(QTY, nullable=False, comment="父批转出量")
    op_type: Mapped[str] = mapped_column(String(20), nullable=False, default="consume", server_default="consume", comment="consume/merge/split/produce")
    op_batch_id: Mapped[int | None] = mapped_column(ForeignKey("batches.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())


class DispenseRecord(Base):
    """配料称重记录：应投 vs 实投 + 容差判定。"""

    __tablename__ = "dispense_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("batches.id"), nullable=False, index=True)
    component_id: Mapped[int | None] = mapped_column(ForeignKey("recipe_components.id"), nullable=True)
    material_id: Mapped[int] = mapped_column(ForeignKey("materials.id"), nullable=False)
    lot_id: Mapped[int | None] = mapped_column(ForeignKey("stock_lots.id"), nullable=True)
    planned_qty: Mapped[Decimal] = mapped_column(QTY, nullable=False)
    actual_qty: Mapped[Decimal] = mapped_column(QTY, nullable=False)
    uom_id: Mapped[int] = mapped_column(ForeignKey("uoms.id"), nullable=False)
    tol_pct: Mapped[Decimal] = mapped_column(RATE, nullable=False, default=Decimal("0"), server_default="0")
    deviated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0", comment="是否超容差")
    operator_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())


# ===================== P2 合规与质量 =====================
# HACCP/CCP、CIP 清洗、CoA 放行、杀菌时间-温度记录。数量统一 DECIMAL(18,4)。


class Ccp(SoftDeleteMixin, Base):
    """HACCP 关键控制点定义：监控参数 + 限值 + 纠偏措施（P2 合规）。"""

    __tablename__ = "ccps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(32), nullable=False, unique=True, comment="CCP 编号，如 CCP-01")
    name: Mapped[str] = mapped_column(String(64), nullable=False, comment="控制点名称，如 杀菌温度")
    process_step: Mapped[str | None] = mapped_column(String(64), nullable=True, comment="关联工序名/op_type")
    param_key: Mapped[str] = mapped_column(String(32), nullable=False, default="temp_c", server_default="temp_c", comment="监控参数键 temp_c/duration_min/ph/conductivity")
    uom_id: Mapped[int | None] = mapped_column(ForeignKey("uoms.id"), nullable=True)
    limit_min: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True, comment="关键限值下限")
    limit_max: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True, comment="关键限值上限")
    target_value: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True, comment="目标值")
    critical: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1", comment="超限即不合格")
    monitor_freq: Mapped[str | None] = mapped_column(String(32), nullable=True, comment="监控频率，如 每批/每小时")
    corrective_action: Mapped[str | None] = mapped_column(Text, nullable=True, comment="纠偏措施")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())


class CcpRecord(Base):
    """CCP 监控记录：实测值 + 限值判定 + 偏差/纠偏（异常告警来源）。"""

    __tablename__ = "ccp_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ccp_id: Mapped[int] = mapped_column(ForeignKey("ccps.id"), nullable=False, index=True)
    batch_id: Mapped[int | None] = mapped_column(ForeignKey("batches.id"), nullable=True, index=True)
    operation_id: Mapped[int | None] = mapped_column(ForeignKey("batch_operations.id"), nullable=True)
    lot_id: Mapped[int | None] = mapped_column(ForeignKey("stock_lots.id"), nullable=True)
    measured_value: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    uom_id: Mapped[int | None] = mapped_column(ForeignKey("uoms.id"), nullable=True)
    measured_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    operator_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pass", server_default="pass", comment="pass/deviation")
    deviation_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    corrective_action: Mapped[str | None] = mapped_column(Text, nullable=True)
    verified_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())


class CipLog(SoftDeleteMixin, Base):
    """CIP 清洗记录：罐/线清洗参数 + 结果（合规留痕）。"""

    __tablename__ = "cip_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    batch_id: Mapped[int | None] = mapped_column(ForeignKey("batches.id"), nullable=True, index=True)
    station: Mapped[str] = mapped_column(String(32), nullable=False, comment="罐/线/工位")
    cip_type: Mapped[str] = mapped_column(String(16), nullable=False, default="tank", server_default="tank", comment="tank/line/cop")
    start_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    end_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    duration_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    caustic_conc_pct: Mapped[Decimal | None] = mapped_column(Numeric(8, 3), nullable=True, comment="碱浓度 %")
    caustic_temp_c: Mapped[Decimal | None] = mapped_column(Numeric(9, 2), nullable=True, comment="碱洗温度 ℃")
    acid_conc_pct: Mapped[Decimal | None] = mapped_column(Numeric(8, 3), nullable=True, comment="酸浓度 %")
    acid_temp_c: Mapped[Decimal | None] = mapped_column(Numeric(9, 2), nullable=True, comment="酸洗温度 ℃")
    rinse_conductivity: Mapped[Decimal | None] = mapped_column(Numeric(12, 3), nullable=True, comment="末次冲洗电导率")
    final_rinse_ph: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True, comment="末次冲洗 pH")
    result: Mapped[str] = mapped_column(String(16), nullable=False, default="pass", server_default="pass", comment="pass/fail")
    operator_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())


class Coa(SoftDeleteMixin, Base):
    """检验报告 / 放行单：原料入库检验、成品放行；判定后锁死不可改（P2）。"""

    __tablename__ = "coa"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    coa_no: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    lot_id: Mapped[int | None] = mapped_column(ForeignKey("stock_lots.id"), nullable=True, index=True)
    material_id: Mapped[int] = mapped_column(ForeignKey("materials.id"), nullable=False)
    batch_id: Mapped[int | None] = mapped_column(ForeignKey("batches.id"), nullable=True, index=True)
    direction: Mapped[str] = mapped_column(String(16), nullable=False, default="incoming", server_default="incoming", comment="incoming(原料)/outgoing(成品)")
    sample_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    tested_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    tester_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    result: Mapped[str] = mapped_column(String(16), nullable=False, default="pending", server_default="pending", comment="pending/pass/fail/hold")
    items: Mapped[list | None] = mapped_column(JSON, nullable=True, comment="检验项目 [{name,spec,value,unit,result}]")
    released_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    released_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    locked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0", comment="判定后锁死，不可修改")
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())


class TempLog(Base):
    """杀菌/工艺时间-温度时间序列：杀菌曲线留痕 + 异常告警（P2）。"""

    __tablename__ = "temp_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    batch_id: Mapped[int | None] = mapped_column(ForeignKey("batches.id"), nullable=True, index=True)
    operation_id: Mapped[int | None] = mapped_column(ForeignKey("batch_operations.id"), nullable=True)
    ccp_id: Mapped[int | None] = mapped_column(ForeignKey("ccps.id"), nullable=True, index=True)
    station: Mapped[str | None] = mapped_column(String(32), nullable=True, comment="罐/线/工位")
    stage: Mapped[str] = mapped_column(String(16), nullable=False, default="hold", server_default="hold", comment="heat/hold/cool")
    recorded_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    temp_c: Mapped[Decimal] = mapped_column(Numeric(9, 2), nullable=False)
    duration_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    in_range: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1", comment="是否在 CCP 限值内")
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())