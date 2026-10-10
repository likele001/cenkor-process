"""初始基线：按 ORM 模型建全部表

Revision ID: 0001_init_schema
Revises:
Create Date: 2026-10-10

绿色基线迁移：直接从 ``Base.metadata`` 生成完整 schema（含 A2 RBAC、A3 审计、
A3-A6 新增列、A7 存储/通知所需结构），DDL 与当前模型定义严格一致。

约定：本迁移作为「空库」基线使用 —— 若库中已存在同名旧表，`create_all` 的
checkfirst 语义只会跳过、不会为已存在表补列。因此首次落地请先在空库（或已
drop 旧表）上执行 `alembic upgrade head`。此后所有 schema 变更须走新的增量迁移。
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

# 触发全部模型注册，并把 Base.metadata 作为建表目标
from app import models  # noqa: F401
from app.models.base import Base

# revision identifiers, used by Alembic.
revision: str = "0001_init_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind(), checkfirst=True)


def downgrade() -> None:
    Base.metadata.drop_all(bind=op.get_bind(), checkfirst=True)
