# Copyright (C) 2026 CenkorProcess Project
# SPDX-License-Identifier: AGPL-3.0
"""RBAC 默认权限点/角色/角色权限预设（幂等种子源）。

权限点命名规范：<域>.<动作>。域对齐流程制造核心模块：
master 主数据 · recipe 配方 · batch 批次/工序 · stock 批次库存 · quality 合规(CCP/CIP/CoA) ·
compliance 记录留痕 · audit 审计 · dashboard 看板 · system 系统管理。
"""

DEFAULT_PERMISSIONS: list[tuple[str, str]] = [
    # 主数据
    ("master.view", "主数据查看"),
    ("master.manage", "主数据管理"),
    # 配方
    ("recipe.view", "配方查看"),
    ("recipe.view_full", "配方完整配比查看（脱敏豁免）"),
    ("recipe.manage", "配方管理"),
    # 批次/工序
    ("batch.view", "批次查看"),
    ("batch.manage", "批次管理"),
    # 批次库存/效期
    ("stock.view", "库存查看"),
    ("stock.manage", "库存管理"),
    # 质量/合规
    ("quality.view", "质量记录查看"),
    ("quality.manage", "质量记录管理"),
    ("compliance.view", "合规记录查看"),
    ("compliance.manage", "合规记录管理"),
    # 审计
    ("audit.view", "审计日志查看"),
    # 看板/报表
    ("dashboard.view", "看板查看"),
    # 系统管理
    ("user.manage", "用户管理"),
    ("role.manage", "角色管理"),
    ("permission.manage", "权限点管理"),
    ("setting.manage", "系统设置"),
]

DEFAULT_ROLES: list[tuple[str, str]] = [
    ("admin", "管理员"),
    ("qc", "质检/合规员"),
    ("operator", "操作工"),
    ("viewer", "只读查看"),
]

ROLE_PERMISSION_PRESETS: dict[str, set[str]] = {
    "admin": {code for code, _ in DEFAULT_PERMISSIONS},
    "qc": {
        "master.view", "recipe.view", "batch.view", "stock.view",
        "quality.view", "quality.manage", "compliance.view", "compliance.manage",
        "audit.view", "dashboard.view",
    },
    "operator": {
        "master.view", "recipe.view", "batch.view", "batch.manage",
        "stock.view", "stock.manage", "quality.view", "compliance.view",
    },
    "viewer": {
        "master.view", "recipe.view", "batch.view", "stock.view",
        "quality.view", "compliance.view", "dashboard.view",
    },
}
