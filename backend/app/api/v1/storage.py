# Copyright (C) 2026 CenkorProcess Project
# SPDX-License-Identifier: AGPL-3.0
"""附件存储端点（A7）：上传 / 签名 / 驱动配置查询。

默认本地驱动；云驱动（aliyun/tencent/qiniu）缺 SDK 或凭据时由工厂自动降级 local。
"""
from fastapi import APIRouter, File, UploadFile

from app.core.config import settings
from app.core.errors import BizError
from app.core.response import ok
from app.storage.base import StorageError
from app.storage.factory import get_active_storage, registered_drivers

router = APIRouter()


@router.get("/storage/config")
def storage_config():
    return ok(
        {
            "driver": settings.STORAGE_DRIVER,
            "available_drivers": registered_drivers(),
            "max_size_mb": settings.STORAGE_MAX_SIZE_MB,
        }
    )


@router.post("/storage/upload")
async def upload_attachment(file: UploadFile = File(...)):
    storage = get_active_storage()
    max_size = int(settings.STORAGE_MAX_SIZE_MB) * 1024 * 1024
    content_type = file.content_type or "application/octet-stream"
    try:
        obj = storage.save(
            filename=file.filename or "file",
            content_type=content_type,
            stream=file.file,
            max_size=max_size,
        )
    except StorageError as exc:
        raise BizError(413, str(exc))
    except ValueError as exc:  # 文件过大等
        raise BizError(400, str(exc))
    url = storage.signed_url(key=obj.key, content_type=content_type, filename=file.filename)
    return ok(
        {
            "driver": obj.driver,
            "key": obj.key,
            "filename": file.filename,
            "content_type": content_type,
            "size": obj.size,
            "sha256": obj.sha256,
            "signed_url": url,
        }
    )


@router.get("/storage/sign")
def sign_url(key: str, expires: int = 3600, content_type: str = "application/octet-stream", filename: str | None = None):
    storage = get_active_storage()
    return ok({"key": key, "signed_url": storage.signed_url(key=key, content_type=content_type, expires=expires, filename=filename)})
