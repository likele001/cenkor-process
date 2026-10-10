# CenkorProcess 架构：核心内核 + 可插拔应用

> 配套文档：开发执行见 `DEVELOPMENT.md`，商业变现见 `COMMERCIAL_PLAN.md`（如有）。
> 前提：本产品 fork CenkorMES 胶水层，Vue3+MySQL，模块化单体；分发挂 cenkor-admin 市场 `product="cenkor-process"`。

## 0. 前提：扩展宿主（可插拔的地基）
宿主机制当前只在 CenkorMES，cenkor-process 尚未移植。需 fork 过来（详见 DEVELOPMENT.md A1）：
- 后端 `app/extension_host/{__init__,manifest,loader,state,host}.py`：扫 `extensions/` → 校验 manifest → 幂等跑 `migrations.sql` → 挂 `/api/extensions/{key}` → 运行期热挂/卸载免重启 → `require_extension(key)` 授权/到期门控（文件态 `.state/`，不建库表）。
- `config.EXTENSIONS_DIR` + `main.py` 启动调 `mount_extensions(app, base)`。
- `api/admin/market/router.py`：在线安装/解压/卸载（复用热加载引擎）。
- 前端：`window.__registerExtension({key,menus,routes})` + 动态路由 + Bearer（token 键 `cenkorpro_admin_token`）。
- 平台侧 cenkor-admin 多产品分发**已原生支持**，无需改。

## 1. 划分原则
- **核心内核**（不可插拔）：被反复依赖的地基对象 + 断链即崩的追溯链 + 合规红线 + 权限/审计地基 + 扩展宿主本身。
- **可插拔应用**：可选增值 / 行业差异 / 硬件相关 / 报表可视化，按需购买安装。

## 2. 核心内核功能（引擎自带）
主数据(单位/换算/物料[含保质期·存储条件·检验标准]/仓库) · 配方(版本/快照/缩放/收率/公差 + 字段级脱敏 + 变更审计) · 批次/工序 · 批次库存(`stock_lot`: lot+效期+FEFO+小数) · 谱系(`lot_genealogy`) · 配料(`dispense_records`) · 正反向追溯查询 · 过期锁定禁投校验 · RBAC + 审计日志 + 逻辑删除 · 存储/通知底座 · 扩展宿主。

## 3. 可插拔应用 backlog（product="cenkor-process"）
| key | 模块 | 功能 | 依赖核心 |
|---|---|---|---|
| compliance_suite | 4 | IQC/IPQC/FQC 分层、放行/扣留、不良库、缺陷TOP、迎检报告 | ccps/coa |
| traceability_recall | 5 | 正反向追溯、召回定位下游发货单、影响面报告 | lot_genealogy |
| shopfloor_pda | 3 | 移动端扫码投料、防混批+效期校验、报工、Andon | dispense/stock_lot/ccp |
| planning_scheduler | 2 | 接单、工单→批次号、APS-lite、齐套缺料预警、插单 | batches/materials |
| barcode_serialization | 6 | 物料/包装条码二维码赋码、出入库扫码 | stock_lot |
| dashboard_report | 7/8 | 看板/大屏、生产/质量/损耗报表、效期·超限预警 | 全域只读聚合 |
| equipment_iot | 7 | PLC/称重/温湿度采集、时序、OEE | temp_logs |
| erp_aps_wms_adapters | 9 | ERP/APS/WMS、扫码枪/电子秤硬件集成 | 主数据/批次 |
| dairy/beverage/bakery/meat/condiment/prepared_meal/brewing | 行业包 | 各细分行业专有字段+流程 | 核心 proc 表 |

## 4. 单个插件包契约
```
<ext_key>/
  manifest.json      # key/name/version/permissions(ext.<key>.view/manage)/menus → /ext/<key>
  router.py          # APIRouter；宿主自动加 get_current_user + require_extension(key)
  migrations.sql     # CREATE TABLE IF NOT EXISTS ext_<key>_...（幂等）
  frontend/plugin.js # window.__registerExtension({key,menus,routes})
  README.md
```
- 开发/打包在仓库外 `/www/wwwroot/process-extensions/<key>/`，zip 根级含 manifest.json。
- 全链路：上传 Hub → 审核 → 定价 → 门户购买 → 安装热生效（由用户操作）。

## 5. 工程纪律（关键）
库存/配方/批次**只有一份真相 = 核心 proc 表**。插件只能【只读 JOIN 核心 + 写自有 `ext_<key>_` 表】，严禁在插件内再造库存/效期——规避当初否决方案 A 的"双库存"陷阱。

## 6. 技术选型定调（拒绝外部规格书的重选型）
- 前端保留 **Vue3+Element Plus**（已 fork，不转 React）；数据库 **MySQL**（不上 PostgreSQL）；**模块化单体**（不做微服务）；设备高频采集/时序库(InfluxDB)/大屏留到 `equipment_iot`（W4）再评估，初期关系表 `temp_logs` 够用；消息用现成 **Celery+Redis**。
- 理由：换栈=放弃 fork 复用的全部优势（登录/RBAC/存储/通知/市场心跳/发布脚本），对中小食品厂 MES 属过度设计。
