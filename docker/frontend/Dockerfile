# Copyright (C) 2026 CenkorProcess Project
# SPDX-License-Identifier: AGPL-3.0
# CenkorProcess 前端生产镜像（管理后台）。
# 构建上下文为仓库根目录；通过 --build-arg FRONTEND 选择前端源码目录（默认 frontend）。
# 构建产物（dist）由 nginx 托管，/api 就地反代到 backend:8600 容器内部端口。

# ---- 阶段一：依赖安装与生产构建 ----
FROM node:20-alpine AS build
ARG FRONTEND=frontend
WORKDIR /app

COPY ${FRONTEND}/package.json ${FRONTEND}/package-lock.json ./
RUN npm ci --prefer-offline --no-audit --no-fund

COPY ${FRONTEND}/ ./
RUN npm run build

# ---- 阶段二：nginx 运行时 ----
FROM nginx:1.27-alpine
COPY docker/nginx/frontend.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
STOPSIGNAL SIGTERM
