# Copyright (C) 2026 CenkorProcess Project
# SPDX-License-Identifier: AGPL-3.0
"""Alembic 迁移冒烟（CI 用）：空 sqlite 上 upgrade head → 校验建表数 → downgrade base。

证明迁移链完整、基线能建出全部模型表、且可干净回滚。不落任何真实库。
用法：DB_URL=sqlite:///./ci_smoke.db python scripts/smoke_alembic.py
"""
from __future__ import annotations

import os
import pathlib
import subprocess
import sys


def _backend_dir() -> str:
    return str(pathlib.Path(__file__).resolve().parents[1])


def _alembic(*args: str) -> None:
    cmd = [sys.executable, "-m", "alembic", *args]
    print("+", " ".join(cmd))
    subprocess.run(cmd, cwd=_backend_dir(), check=True)


def main() -> int:
    db_url = os.environ.get("DB_URL", "")
    if "sqlite" not in db_url:
        print("!! 冒烟要求 DB_URL 指向 sqlite，避免连真实库。当前:", db_url, file=sys.stderr)
        return 2

    base = pathlib.Path(_backend_dir())
    # 解析 sqlite 文件路径，运行前清理，确保「空库」
    db_path = db_url.split("sqlite:///")[-1].lstrip("/")
    target = (base / db_path) if not os.path.isabs(db_path) else pathlib.Path(db_path)
    for suffix in ("", "-journal", "-wal", "-shm"):
        p = pathlib.Path(str(target) + suffix)
        if p.exists():
            p.unlink()

    # 1) 升级到最新
    _alembic("upgrade", "head")

    # 2) 校验建表数与模型一致
    sys.path.insert(0, str(base))  # 让本进程可导入 app.*
    from sqlalchemy import create_engine, inspect

    from app import models  # noqa: F401  触发注册
    from app.models.base import Base

    engine = create_engine(db_url)
    db_tables = set(inspect(engine).get_table_names())
    model_tables = set(Base.metadata.tables.keys())
    missing = model_tables - db_tables
    print(f"模型表 {len(model_tables)}，库内表 {len(db_tables)}，缺失 {sorted(missing) or '无'}")
    if missing:
        print("!! 基线迁移未建出全部模型表", file=sys.stderr)
        return 1

    # 3) 回滚到底，证明 downgrade 可用、库回到空
    _alembic("downgrade", "base")
    after = set(inspect(create_engine(db_url)).get_table_names())
    leftover = after - {"alembic_version", "sqlite_sequence"}
    print(f"downgrade 后残留业务表 {sorted(leftover) or '无'}")
    if leftover:
        print("!! downgrade 未清空业务表", file=sys.stderr)
        return 1

    print("✅ Alembic 迁移冒烟通过（upgrade→校验→downgrade）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
