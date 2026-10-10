# Copyright (C) 2026 CenkorProcess Project
# SPDX-License-Identifier: AGPL-3.0
"""审计日志表：记录关键业务对象的创建/更新/删除变更历史（旧值/新值/原因/操作人/IP）。

本表为 append-only，不混入 SoftDeleteMixin；禁止对其做任何修改/删除。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    entity: Mapped[str] = mapped_column(String(64), nullable=False, index=True, comment="被审计对象表名")
    entity_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(16), nullable=False, comment="create/update/delete")
    before: Mapped[dict | None] = mapped_column(JSON, nullable=True, comment="变更前的改动字段旧值")
    after: Mapped[dict | None] = mapped_column(JSON, nullable=True, comment="变更后的改动字段新值 / 新建快照")
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True, comment="变更原因（可选）")
    actor_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    actor_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), index=True)
