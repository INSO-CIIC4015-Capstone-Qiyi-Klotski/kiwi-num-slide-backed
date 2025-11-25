# app/core/config.py
import os
from dataclasses import dataclass
from app.core.logging import env_logger as logger


@dataclass
class Settings:
    # --- DB ---
    db_host: str
    db_port: int
    db_name: str
    db_user: str
    db_password: str

    # --- Auth / JWT ---
    jwt_secret: str
    access_token_minutes: int
    refresh_token_days: int

    # --- AWS / SES ---
    aws_region: str
    ses_sender_email: str

    # --- URLs / site ---
    public_base_url: str

    # --- Avatares / S3 ---
    avatar_bucket: str
    avatar_cdn_base: str
    avatar_prefix: str

    # --- Cookies / CSRF ---
    cookie_domain: str
    cross_site_cookies: int

    # --- Daily Puzzle ---
    daily_tz: str
    generation_secret: str | None

    # --- Flags ---
    disable_scheduler: bool


def _get_env(name: str) -> str | None:
    return os.getenv(name)


def _debug_value(name: str, value: str | None):
    """Log DEBUG literal de la variable."""
    logger.debug(f"{name} = {value}")


def load_settings() -> Settings:
    logger.info("🔧 Loading backend environment settings...")

    # -------------------------
    # 1) Required variables
    # -------------------------
    required = {
        "DB_HOST": "db_host",
        "DB_PORT": "db_port",
        "DB_NAME": "db_name",
        "DB_USER": "db_user",
        "DB_PASSWORD": "db_password",
        "JWT_SECRET": "jwt_secret",
        "AWS_REGION": "aws_region",
        "SES_SENDER_EMAIL": "ses_sender_email",
        "PUBLIC_BASE_URL": "public_base_url",
        "AVATAR_BUCKET": "avatar_bucket",
        "AVATAR_CDN_BASE": "avatar_cdn_base",
        "AVATAR_PREFIX": "avatar_prefix",
        "COOKIE_DOMAIN": "cookie_domain",
    }

    raw: dict[str, object] = {}
    missing = []

    for env_var, attr in required.items():
        value = _get_env(env_var)
        _debug_value(env_var, value)

        if not value:
            missing.append(env_var)

        raw[attr] = value

    if missing:
        logger.error(f"❌ Missing required env vars: {', '.join(missing)}")
        raise RuntimeError("Missing required environment variables")

    # -------------------------
    # 2) Optional variables
    # -------------------------
    atm = _get_env("ACCESS_TOKEN_MINUTES")
    _debug_value("ACCESS_TOKEN_MINUTES", atm)
    raw["access_token_minutes"] = int(atm) if atm else 60

    rtd = _get_env("REFRESH_TOKEN_DAYS")
    _debug_value("REFRESH_TOKEN_DAYS", rtd)
    raw["refresh_token_days"] = int(rtd) if rtd else 3

    daily_tz = _get_env("DAILY_TZ")
    _debug_value("DAILY_TZ", daily_tz)
    raw["daily_tz"] = daily_tz or "UTC"

    gen = _get_env("GENERATION_SECRET")
    _debug_value("GENERATION_SECRET", gen)
    raw["generation_secret"] = gen

    csc = _get_env("CROSS_SITE_COOKIES")
    _debug_value("CROSS_SITE_COOKIES", csc)
    raw["cross_site_cookies"] = int(csc) if csc else 0

    raw["disable_scheduler"] = _get_env("DISABLE_SCHEDULER") == "1"

    _debug_value("DISABLE_SCHEDULER", raw["disable_scheduler"])

    # -------------------------
    # 3) Type conversion
    # -------------------------
    try:
        raw["db_port"] = int(raw["db_port"])
    except Exception:
        logger.error("ENV DB_PORT must be an integer")
        raise

    # -------------------------
    # 4) Final settings object
    # -------------------------
    settings = Settings(**raw)

    logger.info("✅ Environment variables loaded OK")
    return settings


settings = load_settings()
