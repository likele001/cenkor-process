# Copyright (C) 2026 CenkorProcess Project
# SPDX-License-Identifier: AGPL-3.0
"""WebSocket 推送端点（A7）：客户端连上后接收 notify/刷新事件。

连接后保持读取（用于客户端心跳/指令）；断开即从连接池移除。
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.services.ws_hub import ws_hub

router = APIRouter()


@router.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws_hub.connect(ws)
    try:
        await ws.send_json({"type": "connected", "clients": ws_hub.client_count})
        while True:
            # 客户端可发送任意文本作为心跳；服务端仅下行推送
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    except Exception:  # noqa: BLE001 - 连接异常同样清理
        pass
    finally:
        await ws_hub.disconnect(ws)
