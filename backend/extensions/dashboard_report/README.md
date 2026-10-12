# 经营驾驶舱与数据大屏（dashboard_report）

面向食品/流程制造（cenkor-process）的**跨域 BI 经营驾驶舱 / 数据大屏**付费商业扩展。把散落在各分析应用的核心 KPI 聚合成一屏，支持目标/警戒阈值红绿灯判定与全屏大屏挂墙。

## 卖点
- **五域一屏**：生产（完成批次/产出/收率）、质量（CCP 合格率/CoA 合格率/偏差/不合格）、物料（投料超差率）、清洗（CIP 失败）、库存（临期/过期/隔离量）统一呈现。
- **目标红绿灯**：为任意 KPI 设目标值与警戒值 + 越优方向（越大/越小越好），实时算达成率并按绿/橙/红着色。
- **趋势 + 告警**：近 N 天完成批次/产出趋势条形；过期/临期批次、CCP 偏差、检验不合格、投料超差汇成风险告警清单。
- **大屏模式**：一键切深色全屏挂墙看板，自动 30s 刷新。
- **零侵入**：只建 `ext_dsh_target` 存阈值配置，指标值全部实时只读聚合自核心表，不改业务数据。

## 后端接口（前缀 `/api/extensions/dashboard_report`）
| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/cockpit?days` | 五域 KPI 快照 + 目标达成红绿灯 |
| GET | `/trend?days` | 完成批次/产出/收率日趋势 |
| GET | `/alerts?limit` | 跨域风险告警清单 |
| GET | `/screen?days` | 大屏聚合快照（cockpit + trend + alerts 一次返回） |
| GET | `/targets` | 已配置阈值 + 内置指标目录 |
| POST | `/targets` | upsert 某指标的目标/警戒/方向 |
| DELETE | `/targets/{metric_key}` | 清除某指标阈值 |

## 权限
- `ext.dashboard_report.view`：查看驾驶舱与大屏
- `ext.dashboard_report.manage`：维护 KPI 目标与警戒阈值

## 前端
侧栏「经营驾驶舱」，路由 `/ext/dashboard-report`：时间窗切换、KPI 分组卡、趋势、告警、目标设置面板、进入大屏模式。

## 安装
安装时执行 `migrations.sql`（幂等，`COLLATE=utf8mb4_general_ci`）。无后台线程。
