# Copyright (C) 2026 CenkorProcess Project
# SPDX-License-Identifier: AGPL-3.0
"""扩展宿主：极薄的可插拔扩展加载机制（A1，移植自 CenkorMES）。

- 扫描 ``EXTENSIONS_DIR`` 下每个子目录（含 manifest.json 的扩展包）
- 校验 manifest、执行幂等迁移、挂载 ``/api/extensions/{key}`` 路由
- 请求级门控：未启用（本地禁用 / 授权非 active）返回 403
- 运行期热挂/热卸（直接增删 app.router.routes），无需重启

应用目录、发卡、实例绑定、吊销等管理动作属于商业化阶段（B），
底座阶段默认失败开放（装了即启用），本地可 enable/disable 覆盖。
"""
from .host import (  # noqa: F401
    extensions_base_dir,
    hot_setup_extension,
    hot_teardown_extension,
    mount_all,
    startup_host,
)
from .loader import rescan_extensions  # noqa: F401
from .state import runtime  # noqa: F401
