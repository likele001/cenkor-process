# Copyright (C) 2026 CenkorProcess Project
# SPDX-License-Identifier: AGPL-3.0
"""扩展声明文件（manifest.json）的读取与校验。

manifest v1 结构::

    {
      "key": "quotation_demo",           # 必填，须与扩展目录名一致
      "name": "报价单（演示）",           # 必填
      "version": "1.0.0",                # 必填
      "description": "",                  # 可选
      "icon": "Document",                 # 可选
      "category": "sales",                # 可选
      "vendor": "",                       # 可选
      "permissions": [                    # 可选，启用时注入权限点并补授 admin
        {"code": "ext.quotation.view", "name": "查看报价"}
      ],
      "menus": [                          # 可选，前端加载器动态注入菜单
        {"title": "报价单", "path": "/ext/quotation", "icon": "Document", "permission": "ext.quotation.view"}
      ]
    }
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path


class ManifestError(ValueError):
    """manifest 不合法。"""


# 扩展 key 同时是目录名，直接参与路径拼接；必须在入口挡住 `..`、`/`、绝对路径等。
KEY_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")


def is_valid_key(key: str) -> bool:
    """扩展 key 是否安全（字母数字开头，仅 _ . -，最长 64 字符）。"""
    return bool(KEY_RE.fullmatch(str(key or "")))


@dataclass
class ExtensionManifest:
    """扩展清单。"""

    key: str
    name: str
    version: str
    description: str = ""
    icon: str = ""
    category: str = ""
    vendor: str = ""
    permissions: list[dict] = field(default_factory=list)
    menus: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "icon": self.icon,
            "category": self.category,
            "vendor": self.vendor,
            "permissions": self.permissions,
            "menus": self.menus,
        }


def load_manifest(ext_dir: Path, check_dir_name: bool = True) -> ExtensionManifest:
    """读取并校验扩展目录下的 manifest.json。

    check_dir_name=False 用于安装场景（此时 manifest 尚未落入以 key 命名的目录）。
    """
    file = ext_dir / "manifest.json"
    if not file.is_file():
        raise ManifestError(f"缺少 manifest.json: {file}")
    try:
        raw = json.loads(file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise ManifestError(f"manifest.json 读取失败: {e}")
    if not isinstance(raw, dict):
        raise ManifestError("manifest.json 必须是 JSON 对象")
    for name in ("key", "name", "version"):
        value = raw.get(name)
        if not value or not isinstance(value, str):
            raise ManifestError(f"manifest.json 缺少必填字段 {name}")
    if not is_valid_key(raw["key"]):
        raise ManifestError(
            f"manifest key 非法（仅允许字母数字及 _ . -，且不得以符号开头）：{raw['key']!r}"
        )
    if check_dir_name and ext_dir.name != raw["key"]:
        raise ManifestError(f"manifest key（{raw['key']}）与目录名（{ext_dir.name}）不一致")

    permissions = raw.get("permissions") or []
    if not isinstance(permissions, list):
        raise ManifestError("permissions 必须是数组")
    menus = raw.get("menus") or []
    if not isinstance(menus, list):
        raise ManifestError("menus 必须是数组")

    return ExtensionManifest(
        key=raw["key"],
        name=raw["name"],
        version=raw["version"],
        description=str(raw.get("description") or ""),
        icon=str(raw.get("icon") or ""),
        category=str(raw.get("category") or ""),
        vendor=str(raw.get("vendor") or ""),
        permissions=[p for p in permissions if isinstance(p, dict) and p.get("code")],
        menus=[m for m in menus if isinstance(m, dict) and m.get("path")],
    )
