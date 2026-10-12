-- 订单与生产计划扩展（order_planning）自建表。
-- 纪律：只建 ext_op_* 表；对核心 materials/recipes/stock_lots/batches 仅只读引用（不建外键到核心、不加核心列）。
-- 数量统一 DECIMAL(18,4)；语句幂等（IF NOT EXISTS）；MySQL 方言。

CREATE TABLE IF NOT EXISTS ext_op_orders (
  id            BIGINT PRIMARY KEY AUTO_INCREMENT,
  order_no      VARCHAR(32)  NOT NULL COMMENT '销售订单号',
  customer_name VARCHAR(128) NOT NULL COMMENT '客户名称',
  customer_code VARCHAR(64)  NULL     COMMENT '客户编码',
  status        VARCHAR(16)  NOT NULL DEFAULT 'draft' COMMENT 'draft/confirmed/released/partial_shipped/shipped/closed/cancelled',
  order_date    DATE         NULL,
  due_date      DATE         NULL     COMMENT '整单交期',
  remark        VARCHAR(255) NULL,
  created_by    BIGINT       NULL,
  is_deleted    TINYINT      NOT NULL DEFAULT 0,
  created_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uq_op_order_no (order_no),
  KEY idx_op_order_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS ext_op_order_items (
  id             BIGINT PRIMARY KEY AUTO_INCREMENT,
  order_id       BIGINT        NOT NULL,
  material_id    BIGINT        NOT NULL COMMENT '成品物料 id（核心 materials.id，只读）',
  spec           VARCHAR(128)  NULL     COMMENT '规格/口味/克重/包装',
  qty            DECIMAL(18,4) NOT NULL,
  uom_id         BIGINT        NOT NULL,
  delivered_qty  DECIMAL(18,4) NOT NULL DEFAULT 0 COMMENT '已发货累计',
  due_date       DATE          NULL,
  created_at     DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY idx_op_item_order (order_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS ext_op_plans (
  id            BIGINT PRIMARY KEY AUTO_INCREMENT,
  plan_no       VARCHAR(32)   NOT NULL COMMENT '计划单号',
  source_type   VARCHAR(8)    NOT NULL DEFAULT 'mto' COMMENT 'mto 接单 / mts 备货',
  order_id      BIGINT        NULL     COMMENT 'MTO 关联订单',
  order_item_id BIGINT        NULL     COMMENT 'MTO 关联订单行',
  material_id   BIGINT        NOT NULL COMMENT '成品物料 id（只读）',
  recipe_id     BIGINT        NOT NULL COMMENT '配方 id（核心 recipes.id，只读）',
  planned_qty   DECIMAL(18,4) NOT NULL,
  uom_id        BIGINT        NOT NULL,
  warehouse_id  BIGINT        NULL     COMMENT '投料/产出仓库',
  due_date      DATE          NULL,
  status        VARCHAR(16)   NOT NULL DEFAULT 'draft' COMMENT 'draft/released/in_production/completed/closed/cancelled',
  remark        VARCHAR(255)  NULL,
  created_by    BIGINT        NULL,
  is_deleted    TINYINT       NOT NULL DEFAULT 0,
  created_at    DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at    DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uq_op_plan_no (plan_no),
  KEY idx_op_plan_status (status),
  KEY idx_op_plan_order (order_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 计划 ↔ 核心批次 映射：替代给核心 batches 加 plan_id 列
CREATE TABLE IF NOT EXISTS ext_op_plan_batches (
  id          BIGINT PRIMARY KEY AUTO_INCREMENT,
  plan_id     BIGINT        NOT NULL,
  batch_id    BIGINT        NOT NULL COMMENT '核心 batches.id（只读引用）',
  planned_qty DECIMAL(18,4) NOT NULL,
  created_at  DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uq_op_plan_batch (plan_id, batch_id),
  KEY idx_op_pb_plan (plan_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 成品批次 lot → 订单行 分配/发货（MTS 履约与 MTO 直发都走这里）
CREATE TABLE IF NOT EXISTS ext_op_allocations (
  id           BIGINT PRIMARY KEY AUTO_INCREMENT,
  order_item_id BIGINT        NOT NULL,
  lot_id        BIGINT        NOT NULL COMMENT '核心 stock_lots.id（只读引用）',
  qty           DECIMAL(18,4) NOT NULL,
  shipped       TINYINT       NOT NULL DEFAULT 0,
  shipped_at    DATETIME      NULL,
  created_by    BIGINT        NULL,
  created_at    DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY idx_op_alloc_item (order_item_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 安全库存备货策略（MTS 驱动源）：按 (成品物料, 仓库) 维护 min/max。
-- 只读核心 materials/stock_lots，不建外键到核心。on_hand 由查询实时算，不落库。
CREATE TABLE IF NOT EXISTS ext_op_safety_stock (
  id           BIGINT PRIMARY KEY AUTO_INCREMENT,
  material_id  BIGINT        NOT NULL COMMENT '成品物料 id（核心 materials.id，只读）',
  warehouse_id BIGINT        NOT NULL COMMENT '备货仓库（核心 warehouses.id，只读）',
  min_qty      DECIMAL(18,4) NOT NULL DEFAULT 0 COMMENT '再订货点：低于此值触发备货建议',
  max_qty      DECIMAL(18,4) NOT NULL DEFAULT 0 COMMENT '目标库存：建议补到 max_qty',
  remark       VARCHAR(255)  NULL,
  created_at   DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at   DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uq_op_ss_mat_wh (material_id, warehouse_id),
  KEY idx_op_ss_wh (warehouse_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
