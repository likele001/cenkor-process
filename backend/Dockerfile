# Copyright (C) 2026 CenkorProcess Project
# SPDX-License-Identifier: AGPL-3.0
# CenkorProcess 后端镜像。构建上下文为仓库根目录。
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app

WORKDIR /app

# 数据库驱动基于纯 Python 的 PyMySQL，无需 mysqlclient / gcc 编译链。
# 依赖轻量（无 numpy/scipy），不需要 OpenMP 运行库。
# pip 源做成可覆盖参数：国内部署可传 --build-arg PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
ARG PIP_INDEX_URL=https://pypi.org/simple
COPY backend/requirements.txt .
RUN pip install --upgrade pip --index-url ${PIP_INDEX_URL} \
    && pip install --no-cache-dir -r requirements.txt --index-url ${PIP_INDEX_URL}

COPY backend/ .

RUN mkdir -p /app/data

EXPOSE 8600

COPY docker/scripts/entrypoint-api.sh /entrypoint-api.sh
RUN chmod +x /entrypoint-api.sh

ENTRYPOINT ["/entrypoint-api.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8600"]
