# CenkorProcess 部署与运维手册

> 产品：食品/流程制造独立产品 `cenkor-process`。源码目录 `/www/wwwroot/cenkor-process`（独立仓库，非 cenkormes 工作区）。
> 版本源：根 `VERSION`（当前 `v0.1.0`）。
> **运维纪律**：服务重启、git commit/push、改生产库（DROP/ALTER/迁移执行）、扩展上传安装等动作一律由运维人员手动执行；本手册只给经过验证的命令清单。

---

## 0. 关键事实（速查）

| 项 | 值 |
|---|---|
| 后端框架 / 端口 | FastAPI，容器内 `8600`；宿主默认 `8600`（`.env` 的 `APP_PORT` 覆盖） |
| 管理前端 | 容器内 nginx，宿主默认 `8082`（`WEB_ADMIN_PORT`），`/api` 反代 `backend:8600` |
| 数据库 | MySQL 8，库 `cenkorpro`，驱动 PyMySQL（`mysql+pymysql://`） |
| 缓存 | Redis 7（`REDIS_URL`）；缺失时 WS 退回进程内存态，不阻断启动 |
| Schema 管理 | **Alembic 版本化**（`backend/alembic/` + `alembic.ini`），`DB_AUTO_CREATE=false` |
| 健康检查 | `GET /api/health` → HTTP 200 |
| 默认账号 | `admin` / `admin123`（首启种子创建，生产务必改密） |

---

## 1. 部署方式

### 方式 A · Docker 全栈（推荐）
```bash
cd /www/wwwroot/cenkor-process
cp .env.example .env            # 生产务必设置强随机 JWT_SECRET（≥32 位）
docker compose up -d --build    # 起 mysql + redis + backend + web-admin
```
- 后端容器入口 `docker/scripts/entrypoint-api.sh` 会：等待 MySQL 就绪 → **自动执行 `alembic upgrade head`** → 起 uvicorn。
- 首次启动后，默认管理员/演示种子由应用 startup（`DB_AUTO_SEED=true` 幂等）写入。
- 停止：`docker compose down`（保留数据卷）；销毁含数据：`docker compose down -v`。

### 方式 B · 本地直跑（开发）
```bash
cd /www/wwwroot/cenkor-process/backend
cp .env.example .env            # DB_URL 指向一个已存在的 cenkorpro 库
python3 -m venv venv && venv/bin/pip install -r requirements.txt
venv/bin/python -m alembic upgrade head                 # 建表/升级 schema
venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8600
```
本地需先手动建库（**建库不建表**，表由 alembic 创建）：
```sql
CREATE DATABASE cenkorpro CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

---

## 2. 数据库迁移（Alembic）

所有命令在 `backend/` 目录执行；连接串由 `alembic/env.py` 从 `settings.DB_URL` 注入（`alembic.ini` 不含凭据）。Docker 下也可 `docker compose exec backend python -m alembic <子命令>`。

### 2.1 常用命令
| 目的 | 命令 |
|---|---|
| 升级到最新 | `python -m alembic upgrade head` |
| 升级到指定版本 | `python -m alembic upgrade <rev>` |
| 回滚一版 | `python -m alembic downgrade -1` |
| 回滚到基线（**删光业务表**，慎用） | `python -m alembic downgrade base` |
| 查看当前库版本 | `python -m alembic current` |
| 查看迁移头（应单头，无分叉） | `python -m alembic heads` |
| 查看迁移历史 | `python -m alembic history` |
| 生成新迁移（改模型后） | `python -m alembic revision --autogenerate -m "说明"` |

### 2.2 基线说明
`alembic/versions/0001_init_schema.py` 直接按 `Base.metadata` 建**全部模型表**（当前 22 张，含 A2 RBAC、A3 audit_logs 与软删列、A4/A6 新增列）。它依赖 `checkfirst` 语义——**只建缺失表，不会为已存在表补列**。

### 2.3 首次落地：空库重建（本项目采用）
若目标库存在 create_all 遗留的**缺表/缺列**旧结构（例如只有 proc 域表、无 `permissions/roles/audit_logs`），必须先清空再建，否则基线迁移不会补齐差异：
```sql
-- 确认为 dev/演示数据、无需保留后执行（生产禁止直接 DROP，应走增量迁移）
DROP DATABASE cenkorpro;
CREATE DATABASE cenkorpro CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```
```bash
cd backend && python -m alembic upgrade head
```

### 2.4 后续变更流程（有真实数据后）
1. 改 `app/models/*.py`；
2. `python -m alembic revision --autogenerate -m "..."` 生成增量迁移；
3. **人工校对**生成的 `upgrade()/downgrade()`（autogenerate 不覆盖命名约束、数据迁移、类型细节）；
4. 先在预发/备份库演练 `upgrade head`，确认无误再上生产；
5. 生产始终保持 `DB_AUTO_CREATE=false`，schema 完全由 alembic 管。

### 2.5 备份（迁移前必做）
```bash
mysqldump -h<HOST> -ucenkorpro -p --single-transaction --default-character-set=utf8mb4 cenkorpro > backup_$(date +%F).sql
```

---

## 3. 持续集成（CI）

`.github/workflows/ci.yml`：PR / push 到 master·main 时自动跑（全程 SQLite，**不连真实 MySQL**）：
1. `import app.main` —— 后端装配自检；
2. `python scripts/smoke_alembic.py` —— 空 SQLite 上 `upgrade head` → 校验建表数=模型数 → `downgrade base` 回滚。

迁移链断裂或基线漏建表 → CI 变红不可合并。手动本地复现同一条冒烟：
```bash
cd backend && DB_URL="sqlite:///./ci_smoke.db" python scripts/smoke_alembic.py
```

---

## 4. 扩展宿主（可插拔 · 免重启热装卸）

扩展目录由 `.env` 的 `EXTENSIONS_DIR`（默认 `./extensions`）指定；总开关 `EXTENSIONS_ENABLED`。
- **管理端点**（写操作需 `setting.manage`）：
  - `GET /api/v1/extensions` 已装列表与启用态；
  - `POST /api/v1/extensions/rescan` 重扫目录：新装热挂、移除热卸、补跑扩展 `migrations.sql` 与权限注入，**即时生效无需重启**；
  - `POST /api/v1/extensions/{key}/enable|disable`；`DELETE /api/v1/extensions/{key}` 运行期卸载路由。
- 扩展包契约：`manifest.json` + `router.py`（`router=APIRouter()`）+ 幂等 `migrations.sql`（`CREATE TABLE IF NOT EXISTS ext_<key>_*`）+ 可选 `frontend/plugin.js`。扩展表统一 `ext_<key>_` 前缀，只读 JOIN 核心表、不重建库存/效期。
- 扩展开发在**仓库外**目录进行；产物 ZIP 根级含 `manifest.json`。

---

## 5. 部署后验证（重启由运维手动执行）

> 后端进程一律由运维本人重启；以下为验证与（供参考的）重启动作。

1. 迁移到位：`python -m alembic current` 显示 head；`SHOW TABLES;` 含 `permissions/roles/audit_logs` 等新表。
2. 健康：`curl -i http://<IP>:8600/api/health` → HTTP 200。
3. 登录：`admin/admin123` 取 token；非 superuser 用户按角色受限。
4. 权限：viewer 调写端点 → `code:403`；admin → 放行。
5. 审计：改配方/批次后 `GET /api/v1/audits` 有 before/after 字段级差异留痕。
6. 扩展：`/api/v1/extensions` 可见；`/api/extensions/<key>/ping` 生效；`rescan` 后装卸即时生效。

Docker 重启（供运维参考）：`docker compose restart backend`
宝塔/进程托管：由运维按其管理面板或 `ps -o pid,lstart,etime,cmd -p <pid>` 核对后手动重启。

---

## 6. 常见故障

| 症状 | 根因 | 处理 |
|---|---|---|
| 启动/接口报「no such table」或「Unknown column」 | 库 schema 落后于模型（新表/新列未建） | `alembic upgrade head`；若旧表缺列且为 dev 数据 → 走 §2.3 空库重建 |
| 迁移报 `1050 Table already exists` | `DB_AUTO_CREATE=true` 时应用 startup 抢先 `create_all` | 保持 `DB_AUTO_CREATE=false`；已确认结构等价则 `alembic stamp head` 收口（仅改版本元数据） |
| 扩展卸载后仍能访问 | 旧版 FastAPI 摊平路由 vs 新版 `_IncludedRouter` | 已适配（按 `include_context.prefix` 匹配）；确保部署的是含修复代码并重启 |
| 前端 `/api` 404 / 跨域 | nginx 反代路径或 CORS | 核对 `docker/nginx/frontend.conf` 的 `/api` → `backend:8600`；`.env` 的 `CORS_ORIGINS` |
| JWT 校验异常/重启即失效 | 未设固定 `JWT_SECRET` | 生产在 `.env` 固定强随机值后重启，勿依赖临时兜底生成 |

---

## 7. 版本发布
```bash
cd /www/wwwroot/cenkor-process
bash scripts/release-all.sh [major|minor|patch] [--dry-run] [--no-push]
```
- 默认粒度 `patch`；默认提交并推送（`--no-push` 仅本地）；`--dry-run` 只演练不落库。
- 脚本递增根 `VERSION`（`vMAJOR.MINOR.PATCH`）并 `git commit`（`chore(release): bump version to ...`）。
- 发布后需由运维重启后端使新代码与新 schema（如有迁移）生效。
