# Copyright (C) 2026 CenkorProcess Project
# SPDX-License-Identifier: AGPL-3.0
"""Alembic 迁移运行环境。

- 数据库连接串取自 ``app.core.config.settings.DB_URL``（与后端运行时同源，避免双份配置）。
- ``target_metadata`` 指向 ``app.models.Base.metadata``，使 ``--autogenerate`` 能对比模型与库差异。
"""
from __future__ import annotations

import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

# 把 backend/ 加入导入路径，保证可直接以 alembic 命令导入 app.*
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from alembic import context  # noqa: E402

from app.core.config import settings  # noqa: E402
from app import models  # noqa: E402,F401  - 触发全部模型注册到 Base.metadata
from app.models.base import Base  # noqa: E402

config = context.config

# 用运行时配置覆盖 alembic.ini 中的连接串（ini 里不硬编码凭据）
config.set_main_option("sqlalchemy.url", settings.DB_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """离线模式：仅按 URL 生成 SQL，不建立真实连接。"""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """在线模式：建立连接执行迁移。"""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
