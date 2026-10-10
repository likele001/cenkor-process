# CenkorProcess（流程制造引擎 · P1 骨架）

食品 / 流程制造的**独立第二产品**（决策 C）。复用 CenkorMES 的胶水层，领域内核以
「配方 + 批次(lot) + 罐/线 + 效期(FEFO) + 谱系」为一级对象重建。详见 `cenkor-process开发计划.md`。

## 目录

```
backend/
  app/
    core/        # 胶水层：config / db / response / errors / deps（fork 自 CenkorMES）
    models/proc.py       # 领域模型，全部 proc_ 前缀
    schemas/proc.py
    services/
      recipe_service.py  # 配方缩放 + 批次快照
      stock_service.py   # FEFO 出库 / 收货 / 谱系
      batch_service.py   # 批次产出入账（单事务原子）
    api/v1/      # master / recipe / batch / stock
    main.py      # 入口 + 幂等种子
```

## 运行

```bash
cd /www/wwwroot/cenkor-process/backend
cp .env.example .env      # 填 DB_URL
python3 -m venv venv
venv/bin/pip install -r requirements.txt
venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8600
```

- 端口 **8600**（已确认与服务器现有服务不冲突）。
- 数据库：`cenkorpro` / 账号 `cenkorpro`（独立于 cenkormes 的库与账号）。
- 首次启动自动 `create_all` 建表 + 写入演示种子（单位/仓库/物料/配方/批次库存）。
- `API_KEY` 留空时 dev 放行。

### 端到端验收（进程内跑，不监听端口、不起常驻服务）

```bash
cd /www/wwwroot/cenkor-process/backend
PYTHONPATH=. venv/bin/python scripts/validate_flow.py
```

覆盖：配方缩放 → FEFO 预演 → 建批次 → 产出入账（自动发料 + 谱系）→ 结余核对。

## 关键接口（前缀 `/api`）

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/health` | 健康检查 |
| GET/POST | `/api/v1/uoms` | 单位 |
| GET/POST | `/api/v1/materials` | 物料 |
| GET/POST | `/api/v1/warehouses` | 仓库 |
| GET/POST | `/api/v1/recipes` | 配方列表 / 创建（含成分） |
| POST | `/api/v1/recipes/{id}/release` | 发布配方 |
| GET | `/api/v1/recipes/{id}/scale?qty=1000` | 按目标批量缩放应投量 |
| GET/POST | `/api/v1/batches` | 批次列表 / 创建 |
| GET | `/api/v1/batches/{id}` | 批次详情（含工序、配料记录） |
| POST | `/api/v1/batches/{id}/complete` | **产出入账（原子过账）** |
| GET | `/api/v1/stock/lots` | 批次库存查询 |
| POST | `/api/v1/stock/lots` | 批次收货 |
| GET | `/api/v1/stock/fefo-preview` | FEFO 出库预演 |
| GET | `/api/v1/stock/genealogy/{lot_id}` | 批次谱系 |

## 演示闭环（启动后）

```bash
# 1) 缩放配方：1000 L 成品 -> 各成分应投量
curl 'http://127.0.0.1:8600/api/v1/recipes/1/scale?qty=1000'

# 2) 建批次
curl -X POST http://127.0.0.1:8600/api/v1/batches \
  -H 'Content-Type: application/json' \
  -d '{"recipe_id":1,"planned_qty":1000,"uom_id":3,"warehouse_id":1}'

# 3) 产出入账（自动按 FEFO 发料）
curl -X POST http://127.0.0.1:8600/api/v1/batches/1/complete \
  -H 'Content-Type: application/json' \
  -d '{"warehouse_id":1,"produced_qty":980,"dispenses":[
        {"component_id":1,"material_id":1,"planned_qty":81.6327,"actual_qty":82,"uom_id":1,"tol_pct":2},
        {"component_id":2,"material_id":2,"planned_qty":938.7755,"actual_qty":940,"uom_id":3,"tol_pct":1}]}'

# 4) 查谱系：成品批的上游原料批
curl http://127.0.0.1:8600/api/v1/stock/genealogy/4
```

> 演示种子里白砂糖有两个批次（`SUGAR-2401` 效期近、`SUGAR-2402` 效期远），
> FEFO 会先扣 2401，可在 `fefo-preview` 中直接看到顺序。

## 命名规范

- 领域表统一 `proc_` 前缀；平台/跨切面表（fork 继承）不带前缀。
- 数量一律 `DECIMAL(18,4)`；kg↔L 走物料密度，不进固定 factor。

## 许可

AGPL-3.0（与 CenkorMES 骨架一致）。