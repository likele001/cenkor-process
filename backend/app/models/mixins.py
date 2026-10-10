# Copyright (C) 2026 CenkorProcess Project
# SPDX-License-Identifier: AGPL-3.0
"""声明式混入：逻辑删除（禁止物理删除关键业务记录）。"""
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer
from sqlalchemy.orm import Mapped, mapped_column


class SoftDeleteMixin:
    """为可撤销业务表提供 is_deleted/deleted_at/deleted_by 三列。

    删除操作转为 UPDATE is_deleted=1，列表查询默认过滤 is_deleted=False；
    合规记录（lot_genealogy/dispense_records/ccp_records/temp_logs/audit_logs）
    有意不混入本 Mixin，保持 append-only、不可删除。
    """

    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0", index=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    deleted_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
