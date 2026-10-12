-- 经营驾驶舱与数据大屏扩展（dashboard_report）自建表。
-- 纪律：只建 ext_dsh_* 表；对核心 batches/ccp_records/coa/dispense_records/cip_logs/stock_lots/materials 一律只读聚合，不改业务数据。
-- 本表存「KPI 目标与警戒阈值」，用于驾驶舱红绿灯达成判定；指标值实时算自核心表，本表只存阈值配置。
-- 字符集/排序须与核心表一致（utf8mb4_general_ci）。MySQL 方言，幂等 IF NOT EXISTS。

CREATE TABLE IF NOT EXISTS ext_dsh_target (
  id           BIGINT PRIMARY KEY AUTO_INCREMENT,
  metric_key   VARCHAR(48)  NOT NULL COMMENT '指标键，如 avg_yield / ccp_pass_rate',
  name         VARCHAR(64)  NULL     COMMENT '展示名（留空则用内置名）',
  better       VARCHAR(8)   NOT NULL DEFAULT 'up' COMMENT '越优方向：up 越大越好 / down 越小越好',
  target_value DECIMAL(18,4) NULL    COMMENT '目标值（达成线）',
  warn_value   DECIMAL(18,4) NULL    COMMENT '警戒值（超过即红/告警）',
  note         VARCHAR(255) NULL,
  updated_by   BIGINT       NULL     COMMENT '最后修改人 user id',
  is_deleted   TINYINT      NOT NULL DEFAULT 0,
  created_at   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uq_dsh_target (metric_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
