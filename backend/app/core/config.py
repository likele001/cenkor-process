# Copyright (C) 2026 CenkorProcess Project
# SPDX-License-Identifier: AGPL-3.0
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    APP_NAME: str = "CenkorProcess Backend"
    APP_ENV: str = "dev"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8600

    DB_URL: str = "mysql+pymysql://cenkorpro:Like123456@127.0.0.1:3306/cenkorpro?charset=utf8mb4"
    DB_ECHO: bool = False
    # schema 已改由 Alembic 版本化管理（`alembic upgrade head`）；默认关闭启动自动建表，
    # 避免 create_all 抢建表与迁移冲突。仅本地临时起库可临时置 True。
    DB_AUTO_CREATE: bool = False
    DB_AUTO_SEED: bool = True

    # §3 闸5 库存负值策略：False=严格（不足即阻断）；True=允许缺口挂末批（先产后结账场景）
    ALLOW_NEGATIVE_STOCK: bool = False

    # 效期临期预警阈值（天）：剩余保质期 < 该值视为临期（仅预警展示/推送，不阻断）
    EXPIRY_WARN_DAYS: int = 30

    # 附件存储（A7）：默认本地；云驱（aliyun/tencent/qiniu）依赖对应 SDK，缺失时自动降级 local
    STORAGE_DRIVER: str = "local"
    STORAGE_LOCAL_ROOT: str = "data/storage"
    STORAGE_MAX_SIZE_MB: int = 20
    PUBLIC_BASE_URL: str = ""          # 本地驱动拼签名/下载地址的对外前缀；为空时返回相对路径

    # Redis / 实时推送（A7）：redis 不可用时 ws_hub 仍为进程内存态，不阻断启动
    REDIS_URL: str = "redis://127.0.0.1:6379/0"

    # 扩展宿主（A1）：可插拔扩展热加载总开关与安装目录（相对 backend/，也可绝对路径）
    EXTENSIONS_ENABLED: bool = True
    EXTENSIONS_DIR: str = "./extensions"

    # P1 骨架：可选 API Key 守卫。为空时（dev）放行；正式接平台 RBAC 前的最小防线。
    API_KEY: str = ""

    # 账号体系（对齐 CenkorMES）：JWT 签发、企业品牌、登录验证码
    JWT_SECRET: str = "change_me_change_me_change_me_to_a_long_random_secret"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480      # 记住登录 8 小时
    REMEMBER_ME_EXPIRE_MINUTES: int = 10080    # 记住登录 7 天
    JWT_SECRET_MIN_LENGTH: int = 32
    PASSWORD_MIN_LENGTH: int = 6

    COMPANY_NAME: str = "辰科工艺"
    LOGO_URL: str = ""                           # 前端品牌 logo（公共 URL，留空则用默认品牌）
    LOGIN_CAPTCHA_ENABLED: bool = False          # 登录图形验证码开关（默认关）

    LOGIN_MAX_FAILURES: int = 10                 # 登录失败锁定阈值（≤0 关闭）
    LOGIN_FAIL_WINDOW_SECONDS: int = 300
    LOGIN_LOCKOUT_SECONDS: int = 300

    CORS_ORIGINS: str = ""
    TRUSTED_HOSTS: str = ""


settings = Settings()