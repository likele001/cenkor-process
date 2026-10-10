-- 演示扩展（demo_hello）自建表：验证宿主幂等迁移。
-- 约定：扩展表统一 ext_<key>_ 前缀，避免撞核心/历史表；语句须幂等（IF NOT EXISTS）。
CREATE TABLE IF NOT EXISTS ext_demo_hello_note (
  id INTEGER PRIMARY KEY,
  note VARCHAR(255)
);
