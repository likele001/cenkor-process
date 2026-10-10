# CenkorProcess 开发文档（底座优先 → 商业应用）

> 状态：开发蓝图。开发顺序 = **先底座（阶段 A），后商业应用（阶段 B）**。商业应用（付费插件）压到最后再做。
> 产品：食品/流程制造独立第二产品 `cenkor-process`（fork CenkorMES 胶水层，Vue3+MySQL，模块化单体）。
> 技术事实（已核）：后端端口 8600、库 cenkorpro、`create_all` 建表（当前无 alembic）；领域模型 `app/models/proc.py` 16 表（业务名，无 `proc_` 前缀）；服务层纯 ORM 无裸 SQL；`User` 模型当前无角色/权限表；`core/deps.py` 仅有 `get_current_user`，无 `require_permissions`；业务端点（master/compliance 等）目前仅 `Depends(get_db)`，即**未鉴权**。

---

## 0. 总纲与约束

**阶段划分**
- **阶段 A · 底座**：让产品"能合规上线 + 可插拔"的核心工程，**先做**。
- **阶段 B · 商业应用**：可单独收费的插件/套件，**最后逐个做**，走市场 `product="cenkor-process"`。

**全局纪律（两个阶段都适用）**
1. **单一真相在核心**：库存/配方/批次只在核心 `proc` 表；插件只读 JOIN 核心 + 写自己的 `ext_<key>_` 表，严禁在插件内再造库存/效期。
2. 数量一律 `DECIMAL(18,4)`；扩展表统一 `ext_<key>_` 前缀（避免撞核心/历史表）。
3. 扩展/插件开发在**仓库外**目录（`/www/wwwroot/process-extensions/<key>/`），zip 根级含 `manifest.json`。
4. 运维动作（重启服务、git commit、上传/安装扩展、改生产库）一律由用户手动执行，助手只给清单与命令。
5. 迁移策略：已引入 **alembic** 版本化管理 schema（`alembic upgrade head`）；`DB_AUTO_CREATE` 默认关（仅本地临时起库才开）。

**里程碑**
- M0 底座骨架可跑（已达成：proc 域 + admin 前端 + validate_flow）
- M1 底座合规化（A1–A8 完成）→ 可给客户试点
- M2 W1 两个付费插件上架 → 可变现
- M3+ 按波次扩商业应用目录

---

# 阶段 A · 底座开发（先做）

> 每张任务卡含：目标 / 改动文件 / 新增表·字段 / 端点 / 服务要点 / 验收。按 A1→A8 依赖顺序推进。

## A1 移植扩展宿主（让产品"可插拔"的前提）
- **目标**：把 CenkorMES 的 `extension_host` 热加载机制搬进 cenkor-process。
- **改动**：
  - 复制 `app/extension_host/{__init__,manifest,loader,state,host}.py`（扫描 `extensions/` → 校验 manifest → 幂等跑 `migrations.sql` → 挂 `/api/extensions/{key}` → 运行期热挂/卸载免重启 → `require_extension(key)` 授权门控）。
  - `core/config.py` 加 `EXTENSIONS_DIR: str = "extensions"`。
  - `main.py`：在 `app.include_router(api_router, prefix="/api")` **之后**调用 `mount_extensions(app, Path(settings.EXTENSIONS_DIR))` 与 `run_extension_migrations(...)`。
  - 复制 `api/admin/market/router.py` 的安装/解压/卸载（复用热加载引擎）。
  - 前端 `frontend/`：移植 `window.__registerExtension({key,menus,routes})` + 动态路由注入；Bearer token 键名用 `cenkorpro_admin_token`。
  - 复制 `extensions/.state/`（文件态，MES 侧不建库表）。
- **验收**：放一个 demo 扩展包进 `extensions/`，`docker compose up` 后其 `/api/extensions/<key>` 路由即时生效、前端菜单自动出现；卸载即时消失，无需重启。

## A2 RBAC 权限体系（当前 User 光秃秃，最高优先）
- **目标**：补齐角色/权限模型与依赖链，供 A3–A8 与插件复用。
- **新增表**（对齐 CenkorMES `seed.py`）：`permissions`(code,name,group) · `roles`(code,name) · `role_permissions` · `user_roles`。`User` 加 `roles` 关系。
- **改动**：`core/deps.py` 补 `get_current_permissions(request, user)`（缓存到 `request.state.permission_codes`）+ `require_permissions([...])` / `require_any_permissions([...])`（从 CenkorMES `app/core/deps.py` 原样搬）。
- **权限点前缀**：`master.* / recipe.* / batch.* / stock.* / quality.* / compliance.* / system.*`。
- **seed**：写默认权限点 + `admin` 角色预设（含"权限点自动补授到 admin 角色"机制，沿用 CenkorMES）。
- **验收**：非 superuser 用户按角色受限；`require_permissions` 单测通过。

## A3 审计日志 + 逻辑删除（合规红线：记录不可篡改）
- **新增表** `audit_logs`：`id, entity, entity_id, action(create/update/delete/approve/release), before_json, after_json, reason, actor_id, actor_name, ip, created_at`。
- **软删字段**（追加到可撤销业务表）：`is_deleted(Boolean,default False), deleted_at, deleted_by` → 加到 `recipes / batches / materials / stock_lots / warehouses / ccps / coa / cip_logs`。
- **append-only 表不加软删**（本就禁删）：`lot_genealogy / dispense_records / ccp_records / temp_logs / audit_logs`。
- **实现**：`event.listen(Session,"after_flush")` 或 service 层显式 `write_audit(db,user,entity,before,after,reason)`；DELETE 端点改为 `UPDATE is_deleted=1` + 写审计；所有 list 查询默认 `WHERE is_deleted=0`。
- **端点**：`GET /api/v1/audits?entity=&entity_id=`（权限 `audit.view`，只读）。
- **验收**：改配方/批次留痕（old/new/reason/actor）；删除后数据仍在库、列表不可见；关键记录无法被物理删除接口抹除。

## A4 配方字段级脱敏 + 变更审计 + 类型区分（食品重点）
- **改动 `proc.py`**：`Recipe` 增 `recipe_type Enum('production','trial')`、`owner_id`。敏感字段：`recipe_components.ratio_pct / tol_pct`。
- **权限**：新增 `recipe.view_full`；无此权限者，序列化 Out 中 `ratio_pct/tol_pct` 置 `None` 或掩码 `"***"`（**后端裁剪，前端拿不到明文**）。
- **变更审计**：发布/改配比走 A3 的 audit（记录 old/new ratio + reason）。
- **端点**：`GET /api/v1/recipes/{id}` 依权限返回；`POST /api/v1/recipes/{id}/revise`（生成新版本 + 审计）。
- **验收**：普通操作员读配方看不到完整配比；改配比必带 reason 且留痕。

## A5 效期锁定 + 临期预警（把 `stock_lots.expiry_at` 用起来）
- **配置**：加 `EXPIRY_WARN_DAYS: int = 30`（或 `settings` key-value 表）。
- **投料/领料拦截**（在 `batch_service.complete` / `stock_service` 发料处）：拒绝 `expiry_at < NOW()` 或 `status != 'released'` 的批次 → 抛 `BizError("过期/未放行批次禁止投料")`；配合 `ALLOW_NEGATIVE_STOCK` 严格模式。
- **临期**：出参加只读 `days_to_expiry`；`< EXPIRY_WARN_DAYS` 触发通知（依赖 A7 通知底座）。
- **状态流转**（可选）：定时扫描把 `stock_lots.status` 置 `near_expiry / expired`（先同步实现，量大再交 Celery）。
- **验收**：过期批次无法被投料；临期批次有预警；`fefo-preview` 顺序符合到期日。

## A6 物料字段补齐（保质期/存储条件/检验标准）
- **改动 `proc.py` Material**：增 `storage_condition(String)`、`quality_std(Text/JSON 检验标准)`（`shelf_life_days` 已有）。
- **验收**：主数据可维护三项；投料/检验可引用。

## A7 存储 + 通知/WebSocket 底座（fork 遗漏项）
- **改动**：从 CenkorMES 复制 `app/storage/`（base/local/factory，先 local）与"统一通知 + WebSocket"模块（`services/ws_hub`、notify dispatcher）；`config.py` 补 `STORAGE_DRIVER / STORAGE_LOCAL_ROOT / REDIS_URL`（当前 requirements 已含 redis）。
- **验收**：附件可上传/签名；A5 预警、A3 关键变更可推送。

## A8 权限真正挂到业务端点（收口，务必做）
- **改动**：`api/v1/*.py` 的 `include_router(...)` 统一加 `dependencies=[Depends(get_current_user)]`；写端点叠 `Depends(require_permissions([...]))`。移除"匿名 API-Key 放行"在生产的影响（`API_KEY` 仅 dev）。
- **验收**：未登录 401；越权写 403；`/api/health` 仍开放。

## A-附 · 迁移策略
- **已落地**：引入 Alembic（对齐 CenkorMES：`env.py` 注入 `settings.DB_URL`、`Base.metadata` 为目标）。基线迁移 `alembic/versions/0001_init_schema.py` 直接按 ORM 元数据建全表（含 A2 RBAC / A3 审计 / A3-A6 新列）。
- **首次部署（空库重建）**：若库中已有 create_all 遗留的旧表（缺表/缺列），先 drop 旧表再 `alembic upgrade head`；`create_all` 的 checkfirst 语义只会跳过、不会为已存在表补列。
- **后续变更**：一律走新增量迁移（`alembic revision --autogenerate -m "..."` 后人工校对），生产 `DB_AUTO_CREATE=false`，schema 完全由 alembic 管。

---

# 阶段 B · 商业应用（付费插件 · 最后开发）

> 每个插件 = 一个 `ext_<key>` 应用，挂 `product="cenkor-process"` 分发/授权。依赖阶段 A 的 RBAC/审计/宿主。开发目录：`/www/wwwroot/process-extensions/<key>/`。

## 单个插件包契约
```
<ext_key>/
  manifest.json      # key/name/version/permissions(ext.<key>.view/manage)/menus → /ext/<key>
  router.py          # from app.core.deps import get_current_user, require_permissions; router=APIRouter()
  migrations.sql     # CREATE TABLE IF NOT EXISTS ext_<key>_...（幂等）
  frontend/plugin.js # window.__registerExtension({key,menus,routes})
  README.md
```
宿主自动加 `get_current_user` + `require_extension(key)`；插件仅只读 JOIN 核心 `proc` 表 + 写自有 `ext_` 表。

## W1（门票·最快变现）
- **compliance_suite**：`ext_cs_iqc_records / ext_cs_ipqc_records / ext_cs_fqc_records`（分层检验单，关联 `batches/stock_lots/materials`）+ 不良现象库 `ext_cs_defects` + 迎检报告导出。端点：各层检验 CRUD + `POST /release`(放行/扣留联动 `coa`)。依赖核心：ccps/coa/stock_lots。验收：来料/过程/成品分层可录、放行回写库存状态、报告一键出。
- **traceability_recall**：正/反向追溯可视化 + 召回单 `ext_rr_recalls` + 成品批→下游发货单定位。依赖核心 `lot_genealogy/stock_lots`（只读）。验收：输入成品批回溯全部原料批/工序参数/检验；生成影响面清单。

## W2（车间+行业）
- **shopfloor_pda**：移动端（H5/Vant4 或 uni-app 复用 MES 栈）扫码领料投料、防混批+效期拦截 UI、工序报工、Andon 呼叫 `ext_sp_andon`。依赖 A5 效期拦截 + dispense。验收：PDA 扫原料批校验合规再投料；异常一键呼叫推送。
- **行业垂直包**（dairy/beverage/bakery/meat/condiment/prepared_meal/brewing）：各行业专有字段+工艺模板（seed 包），核心同构，对应汽配/电子/服装打法。验收：装完即带行业主数据/配方模板。

## W3（计划/赋码/看板）
- **planning_scheduler**：ERP/Excel 接单、工单→批次号、齐套缺料预警 `ext_ps_*`、APS-lite。依赖 batches/materials/stock_lots。
- **barcode_serialization**：物料/包装条码二维码赋码、出入库扫码 `ext_bs_*`。依赖 stock_lot。
- **dashboard_report**：效期/超限预警、良率/损耗驾驶舱、大屏（只读聚合）。

## W4（高单价/集成）
- **equipment_iot**：PLC/称重/温湿度采集适配 + 时序 + OEE（后期可引时序库）。依赖 temp_logs。
- **ai_assistant**：配方推荐/质量根因/智能排产，**用户自备 LLM key**（沿用 MES AI 结论，不自担算力）。
- **erp_aps_wms_adapters**：金蝶/用友 ERP、APS、WMS、钉钉/企微集成（项目制）。

---

## 依赖顺序图
```
A2 RBAC ─┬─ A3 审计/软删 ─ A4 配方脱敏 ─ A8 挂端点
         ├─ A5 效期锁定 ─┐
A7 存储/通知 ────────────┼─→ B: W1 compliance / recall → W2 pda/行业 → W3 → W4
A6 物料字段 ─────────────┘
A1 扩展宿主（贯穿，B 阶段强依赖）
```

## 测试策略
- 集成：仿 CenkorMES `conftest.py`（`sqlite:///:memory:` 建全量表 + 事务回滚），断言落 `crud/service` 层。
- 扩展 `scripts/validate_flow.py`：补"效期拦截、字段脱敏后普通岗无 ratio、软删不可见、审计留痕"用例。
- 插件：各自 `migrations.sql` 幂等 + 端点权限 401/403 + 只读核心 JOIN 不写核心。

## Definition of Done（底座）
A1–A8 全部合入且：未鉴权端点归零；关键记录不可物理删且有审计；过期批次投料被拦；普通岗看不到完整配比；放 demo 扩展包能热挂/热卸；`validate_flow` 全绿。此时才进入阶段 B。

---

## 执行边界（再次声明）
本文档为开发蓝图。**编码由后续会话在具备写权限时逐卡落地；建表/迁移/重启服务/git 提交/扩展上传安装等运维动作全部由用户手动执行。**
