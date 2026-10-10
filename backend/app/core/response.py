# Copyright (C) 2026 CenkorProcess Project
# SPDX-License-Identifier: AGPL-3.0
from typing import Any


def ok(data: Any = None, msg: str = "") -> dict:
    return {"code": 200, "msg": msg, "data": data}


def fail(code: int, msg: str, data: Any = None) -> dict:
    return {"code": code, "msg": msg, "data": data}