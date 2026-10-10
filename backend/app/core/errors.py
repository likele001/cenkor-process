# Copyright (C) 2026 CenkorProcess Project
# SPDX-License-Identifier: AGPL-3.0
class BizError(Exception):
    """业务异常：由全局异常处理器统一转成 {code,msg,data} 响应。"""

    def __init__(self, code: int, msg: str):
        self.code = code
        self.msg = msg
        super().__init__(msg)