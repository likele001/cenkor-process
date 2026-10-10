# Copyright (C) 2026 CenkorProcess Project
# SPDX-License-Identifier: AGPL-3.0
"""重置 dev 库：drop 所有 proc_ 表 -> create_all -> 写入种子。仅用于开发环境。

用途：验收脚本会真实扣减库存/产生负值，跑完用它把库恢复成「初次启动」的干净种子态。
"""
import app.models.proc  # noqa: F401  确保所有表已注册到 metadata
from sqlalchemy import text

from app.core.db import SessionLocal, engine
from app.main import _seed, _seed_compliance
from app.models import Base

with engine.begin() as conn:
    conn.execute(text("SET FOREIGN_KEY_CHECKS=0"))
    for table in reversed(Base.metadata.sorted_tables):
        conn.execute(text(f"DROP TABLE IF EXISTS {table.name}"))
    conn.execute(text("SET FOREIGN_KEY_CHECKS=1"))

Base.metadata.create_all(bind=engine)

db = SessionLocal()
try:
    _seed(db)
    _seed_compliance(db)
finally:
    db.close()

print(f"dev 库已重置并重新种子（{len(Base.metadata.sorted_tables)} 张表）")