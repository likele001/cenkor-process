# 订单与生产计划（order_planning）

> CenkorProcess 付费扩展 · 食品/流程制造的销售订单(MTO)与安全库存备货(MTS)统一驱动生产计划，计划下达自动生成核心生产批次，含齐套缺料预检、成品批→订单分配与发货。

## 1. 定位与卖点
- 把「为什么生产、给谁生产」补在核心批次执行链之上：需求 → 计划 → 下达 → 批次 → 投料/产出/追溯（核心既有能力）。
- **接单型(MTO)**：销售订单行 → 生成计划 → 下达；成品批可回绑订单，整批可追溯回客户（召回友好）。
- **备货型(MTS)**：按安全库存/预测直接建计划 → 下达 → 产出入成品库 → 销售时分配发货。
- **齐套缺料预警**：下达前按配方缩放到计划批量，逐料 FEFO 预演可用量，输出缺口，不足默认阻断（可 `force` 强下）。

## 2. 架构纪律（务必知悉）
- **单一真相在核心**：库存/配方/批次仍只在核心 `materials/recipes/stock_lots/batches`。本插件**只建 `ext_op_*` 表，对核心一律只读 JOIN**。
- **不给核心 `batches` 加列**：「计划↔批次」用映射表 `ext_op_plan_batches` 表达。
- **下达 = 调用核心 `batch_service.create_batch`** 生成真实核心批次，插件不另立批次账。
- **发货合规门控**：`allocatable-lots` 仅列 `status='released'`（已放行）且未过期的成品批；核心产出入库初始为 `received`，须经放行（CoA/QC，属合规模块）后方可发货。

## 3. 数据表（自建）
| 表 | 用途 |
|---|---|
| `ext_op_orders` | 销售订单头（客户/交期/状态） |
| `ext_op_order_items` | 订单行（成品物料+规格+数量，只读引用核心物料） |
| `ext_op_plans` | 生产计划单（source_type=mto/mts、配方、计划量、仓库、状态） |
| `ext_op_plan_batches` | 计划↔核心批次 映射（替代核心加列） |
| `ext_op_allocations` | 成品批 lot → 订单行 分配/发货 |
| `ext_op_safety_stock` | 安全库存备货策略（成品+仓库 min/max，MTS 驱动源；现有量实时算自核心 stock_lots） |

## 4. 状态机
- 订单：`draft → confirmed → released → partial_shipped → shipped`；可 `cancelled`（未发货前）。
- 计划：`draft → released → in_production → completed`（下达即建核心批次；`POST /plans/{id}/sync-status` 按关联核心批次 `produced_qty/状态` 回算，草稿可 `DELETE` 软删）。

## 5. 接口（前缀 `/api/extensions/order_planning`）
- 订单：`GET/POST /orders`、`GET /orders/{id}`、`PUT /orders/{id}`、`POST /orders/{id}/confirm`、`POST /orders/{id}/cancel`
- 计划：`GET/POST /plans`、`GET/PUT /plans/{id}`、`GET /plans/{id}/kitting`、`POST /plans/{id}/release[?force=true]`、`GET /plans/{id}/batches`
- 分配/发货：`GET /orders/{id}/allocatable-lots`、`POST /orders/{id}/allocate`、`POST /allocations/{id}/ship`、`GET /orders/{id}/allocations`
- 安全库存/MTS：`GET/PUT /safety-stock`、`DELETE /safety-stock/{id}`、`GET /mts-suggestions`（现有<最低→补到目标）、`POST /generate-mts`（建议批量落草稿计划）、`POST /safety-stock/scan-alert`（扫描并投递备货预警；后台守护线程按 `ORDER_PLANNING_MTS_SCAN_HOURS`（默认6h，<=0关闭）周期自动扫描）
- 生命周期/清理：`POST /plans/{id}/sync-status`、`DELETE /orders/{id}`、`DELETE /plans/{id}`（软删，仅未下达/草稿）
- 权限：读=登录即可；写=需 `ext.order_planning.manage`。

## 6. 安装
由应用中心（Hub，`product="cenkor-process"`）购买→下发→MES 端安装；安装时自动执行 `migrations.sql`（幂等）并注入权限点、热挂载路由。

## 7. 已知依赖 / 前置
- **前端加载器**：本包 `frontend/plugin.js` 遵循 `window.__registerExtension` 契约；cenkor-process 管理端已内置「扩展动态加载器」(`src/utils/extensionLoader.ts`)，安装后经应用中心触发热加载即渲染菜单与页面（含销售订单/生产计划/备货(MTS) 三视图）。
- **超管权限**：需核心修复「超级管理员拥有扩展注入的 `ext.*` 权限点」（已随本插件一并提交核心 `app/crud/rbac.py`），否则 admin 调用写端点会 403。

## 8. 验收（后端端到端，已实测通过）
下单 → 确认 → 建 MTS 计划 → 齐套(enough) → 下达生成核心批次(PB…) → 核心过账产出 FG 批 → 放行 → 建 MTO 计划 → 分配 → 发货 → 订单 `shipped`、行 `delivered/qty` 平账。

## 9. 版本
- 1.0.0：订单/计划/齐套/下达/分配发货首版。
- 1.1.0：新增安全库存备货策略(MTS 驱动)与备货建议一键生成计划、计划生命周期回算(sync-status)、订单/计划软删除；前端新增「备货(MTS)」视图。
- 1.2.0：发货出库改走核心纪律（行锁 FOR UPDATE + `assert_lot_dispensable` 合规门控，未放行/过期批次禁止出库）+ 发货/低库存事件接入统一通知底座；新增备货预警扫描（手动端点 + 无 Celery 的代际守护线程）；前端订单支持多行明细与详情弹窗。

## 10. 许可
AGPL-3.0（与核心一致）；闭源插件经商业授权分发。
