# CenkorProcess 部署与自检指南

食品 / 流程制造的独立第二产品（决策 C）。复用 CenkorMES 胶水层，领域内核以
「配方 + 批次(lot) + 罐/线 + 效期(FEFO) + 谱系」为一级对象重建。

- 后端内部端口：**8600**　数据库：**cenkorpro**（独立于 cenkormes 的库与账号）
- 管理后台（容器内 nginx，/api 就地反代）：默认 **8082**

---

## 一、跑起来（3 步）

### 方式 A：Docker 一键（推荐）
```bash
cd /www/wwwroot/cenkor-process
cp .env.example .env          # 生产务必改 JWT_SECRET（≥32 位强随机）
docker compose up -d --build   # 起 mysql + redis + backend + web-admin
# 后端 http://<IP>:8600（含 /docs），后台 http://<IP>:8082
```
首启由容器入口自动执行 `alembic upgrade head` 建表（schema 由 Alembic 管理），再应写入演示种子（单位/仓库/物料/配方/批次库存）。

### 方式 B：本地直跑（开发）
```bash
cd backend
cp .env.example .env           # DB_URL 指向一个已存在的 cenkorpro 库
python3 -m venv venv && venv/bin/pip install -r requirements.txt
venv/bin/python -m alembic upgrade head    # 建表/升级 schema（首次部署需先空库）
venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8600
```
本地方式需先手动建库（建库不建表，表由 `alembic upgrade head` 创建）：
```sql
CREATE DATABASE cenkorpro CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

---

## 二、端到端自检（改了表名后必跑一遍最稳）
进程内执行，不监听端口、不起常驻服务：
```bash
cd /www/wwwroot/cenkor-process/backend
PYTHONPATH=. venv/bin/python scripts/validate_flow.py
```
覆盖：配方缩放 → FEFO 预演 → 建批次 → 产出入账（自动发料 + 谱系）→ 结余核对。

演示种子里白砂糖有两个批次（`SUGAR-2401` 效期近、`SUGAR-2402` 效期远），
`fefo-preview` 会先扣 2401，可直接看到先进先到期顺序。

---

## 三、⚠️ 孤儿表注意（去 `proc_` 前缀的一次性影响）
本次已把 16 张领域表由 `proc_*` 前缀改为业务名。`create_all`/基线迁移 **只建表、不删旧表**：
- 若 `cenkorpro` 库**之前已建过 `proc_*` 那批表**，它们会变成孤儿脏表（不影响运行）。
- 最省事：**drop 库重建**（P1 是演示种子、非生产数据）；或手动 `DROP TABLE proc_*;`
```sql
DROP DATABASE cenkorpro;
CREATE DATABASE cenkorpro CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

---

## 四、领域表结构速查（去前缀后，DECIMAL(18,4) 数量）

| 表 | 角色 | 关键点 |
|---|---|---|
| `uoms` / `uom_conversions` | 单位与换算 | kg↔L 走**物料密度**分支，不进固定 factor；material_id 非空=物料专属换算 |
| `warehouses` | 仓库 | — |
| `materials` | 物料 | `base_uom_id`、`density_kg_l`、`shelf_life_days`（推算效期） |
| `recipes` / `recipe_components` | 配方 + 成分 | `ratio_pct` 按目标批量线性缩放；`yield_pct` 收率；发布后版本只读 |
| `batches` / `batch_operations` | 批次 + 工序 | 一等生产对象（对应离散 work_orders）；`recipe_snapshot` 锁版本；工序带温度/时长 |
| `stock_lots` | 批次库存 | `(warehouse,material,lot_no)` 唯一；含 `expiry_at`，FEFO 排序键；数量小数 |
| `lot_genealogy` | 批次谱系 | parent_lot→child_lot，consume/merge/split/produce |
| `dispense_records` | 配料称重 | 应投 vs 实投 + `tol_pct` 容差判定 + `deviated` |
| `ccps` / `ccp_records` | HACCP 关键控制点 | 限值 + 实测偏差（异常告警来源，P2） |
| `cip_logs` | CIP 清洗留痕 | 碱/酸浓度·温度·电导率·pH（P2） |
| `coa` | 检验报告 / 放行 | incoming/outgoing；判定后 `locked` 锁死不可改（P2） |
| `temp_logs` | 杀菌时间-温度 | 曲线留痕 + 是否在 CCP 限值内（P2） |

> 平台/跨切面表（`users` 等）由 fork 继承，不带前缀，与领域表同库。

---

## 五、关键接口（前缀 `/api`）

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/health` | 健康检查 |
| GET/POST | `/api/v1/uoms` · `/materials` · `/warehouses` | 主数据 |
| GET/POST | `/api/v1/recipes` | 配方列表 / 创建（含成分） |
| POST | `/api/v1/recipes/{id}/release` | 发布配方 |
| GET | `/api/v1/recipes/{id}/scale?qty=1000` | 按目标批量缩放应投量 |
| GET/POST | `/api/v1/batches` · GET `/api/v1/batches/{id}` | 批次 |
| POST | `/api/v1/batches/{id}/complete` | 产出入账（原子过账：自动发料 + 谱系） |
| GET/POST | `/api/v1/stock/lots` | 批次库存查询 / 收货 |
| GET | `/api/v1/stock/fefo-preview` | FEFO 出库预演 |
| GET | `/api/v1/stock/genealogy/{lot_id}` | 批次谱系 |

---

## 六、版本发布
```bash
bash scripts/release-all.sh [major|minor|patch] [--dry-run] [--no-push]
```
唯一版本源为根 `VERSION`（格式 `vMAJOR.MINOR.PATCH`）。

## 许可
AGPL-3.0（与 CenkorMES 骨架一致）。
