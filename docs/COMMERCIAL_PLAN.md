# CenkorProcess 商业化与变现方案（Open-Core）

> 状态：规划草案 · **不进入开发，商业应用压到最后再做**（开发顺序见 `DEVELOPMENT.md`，架构见 `ARCHITECTURE.md`）。
> 定位：食品/流程制造独立第二产品。变现打法沿用《CenkorMES monetization-plan》，分发挂 cenkor-admin 市场 `product="cenkor-process"`。

## 一、商业模式
1. **核心引擎开源 AGPL**：食品厂看重"数据自主 + 可审计"，开源核心是信任门票与引流；不靠藏源码变现。
2. **付费插件**：独立私有仓 → 市场分发 → `require_extension(key)` 授权/到期自动停用（CenkorMES 已验证闭环）。
3. **非代码变现（不受 AGPL 约束、更稳）**：私有云托管 + 运维 SLA、实施培训、硬件集成（电子秤/扫码枪/PLC/工控机/标签针式打印）、合规迎检服务（HACCP / GB14881 模板）。

法律前提：AGPL 核心不可收回闭源；Pro/插件走独立私有仓 overlay；尽快补 CLA / 贡献者协议。

## 二、核心 vs 商业应用（边界）
- **核心横切地基**（能上线的必要工程，**非商品**）：RBAC、审计日志、逻辑删除、配方字段级脱敏、效期锁定禁投、扩展宿主、存储/通知底座 → 见 `DEVELOPMENT.md` 阶段 A。
- **商业应用**（可单独收费插件/套件）→ 见下表与 `DEVELOPMENT.md` 阶段 B，全部压到最后开发。

## 三、商业应用目录（未来可售 SKU）
| 档位 | 应用 key | 卖点 | 定价建议 | 波次 |
|---|---|---|---|---|
| 免费·核心自带 | 主数据/基础配方/批次/FEFO库存/基础追溯/CCP记录 | 引流、试用 | ¥0 | 上线即用 |
| ★★★ | compliance_suite | IQC/IPQC/FQC 分层、审计不可篡改、CoA 放行、迎检报告 | ¥9999–19999/年 | W1（门票） |
| ★★★ | traceability_recall | 正反向追溯、召回定位下游发货、影响面报告 | ¥6999–12999/年 | W1 |
| ★★☆ | shopfloor_pda | 移动端扫码投料、防混批+效期拦截、报工、Andon | ¥4999–9999/年·按产线 | W2 |
| ★★☆ | 行业垂直包 dairy/beverage/bakery/meat/condiment/prepared_meal/brewing | 细分行业开箱即用 | ¥4999/套起 | W2 |
| ★★☆ | planning_scheduler | 齐套缺料预警、APS-lite 排程、插单 | ¥9999+/年 | W3 |
| ★★☆ | barcode_serialization | 物料/包装赋码、出入库扫码 | ¥4999/年 | W3 |
| ★★☆ | dashboard_report | 效期/超限预警、良率/损耗驾驶舱、大屏 | ¥6999/年 | W3 |
| ★☆☆ | equipment_iot | PLC/称重/温湿度采集、时序、OEE | ¥19999+/年 | W4 |
| ★☆☆ | ai_assistant | 配方推荐/质量根因/智能排产（用户自备 LLM key） | ¥19999+/年套件 | W4 |
| ★☆☆ | erp_aps_wms_adapters | 金蝶/用友 ERP、APS、WMS、钉钉/企微 | 项目制 | 按需 |

计价维度：订阅(年)为主 + 可选买断；流程制造**按产线/罐区**授权，叠加"按用户"；私有部署按年计费。

## 四、打包分层（抬客单价）
- **入门版**（核心开源，¥0）：跑通 配方-批次-追溯。
- **合规专业版**（合规包 + 追溯召回 + 车间PDA）：主流入口——**"合规=买门票"**，迎检刚需最好卖。
- **数字工厂版**（上述 + 计划 + 赋码 + BI + 设备数采）：中大型/多产线。
- **行业版**（对应行业垂直包 + 数字工厂版）：交付最快、毛利最高。

## 五、上线波次（只排序，不开发）
- W0（当下）：只做架构 + 商业规划，**不进开发**。
- W1：compliance_suite、traceability_recall（监管驱动、最快变现）。
- W2：shopfloor_pda、首批行业包（乳品/饮料）。
- W3：planning_scheduler、barcode_serialization、dashboard_report。
- W4：equipment_iot、ai_assistant、erp_aps_wms_adapters。
排序依据 = 变现速度 × 需求刚性，而非技术难易。

## 六、商业纪律
1. **单一真相在核心**：库存/配方/批次只在核心 proc 表；插件只读 + 自有 `ext_` 表 → 任意插件可组合销售、互不打架。
2. **CLA / 贡献者协议**：AGPL 衍生同样要补；插件放独立私有仓闭源。
3. **门控与授权**：复用 `require_extension` + 到期自动停用，不重造轮子。
4. **AI 不自担算力**：ai_assistant 一律用户自备 LLM key。
5. **合规即卖点即护城河**：审计不可篡改、追溯不断链、GB14881/HACCP 记录留痕——既是监管红线也是付费理由。

## 七、待办（规划阶段，暂不落地）
- [ ] 先完成底座阶段 A（见 DEVELOPMENT.md），使产品可上线（非商品）
- [ ] 补 CLA
- [ ] 搭 `product="cenkor-process"` 市场分类 + 授权/门控骨架
- [ ] W1 两个付费插件（合规 / 追溯召回）作为首批商品，最后再开发
