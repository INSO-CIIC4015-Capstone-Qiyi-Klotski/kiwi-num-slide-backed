# app/core/logging.py
import logging
import os


# --------------------------
# Helper: obtener nivel desde env
# --------------------------
def _get_log_level_from_env(env_name: str, default: str = "INFO") -> int:
    """
    Lee un nivel de log desde ENV (DEBUG, INFO, WARNING, ERROR, CRITICAL).
    Si no coincide, usa el default.
    """
    raw = os.getenv(env_name, default)
    if raw is None:
        return logging.getLevelName(default)

    value = raw.upper().strip()

    mapping = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "WARN": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL,
    }

    level = mapping.get(value)
    if level is None:
        # Si el valor no es válido, registra un warning en el root logger
        logging.warning(f"Invalid log level '{value}' in {env_name}, using default '{default}'")
        level = mapping[default]

    return level


# --------------------------
# Builder para loggers con handler único
# --------------------------
def _build_logger(name: str, env_var: str | None = None, default: str = "INFO") -> logging.Logger:
    logger = logging.getLogger(name)

    # Determinar nivel basado en env
    level = _get_log_level_from_env(env_var, default) if env_var else logging.INFO
    logger.setLevel(level)

    # Añadir handler solo una vez
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            "%(levelname)s:%(name)s:%(message)s"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger


# --------------------------
# Loggers públicos
# --------------------------

# Para validación de variables de entorno
env_logger = _build_logger("config", env_var="ENV_LOG_LEVEL", default="INFO")

# Para eventos generales del backend (scheduler, lógica, etc.)
app_logger = _build_logger("app", env_var="APP_LOG_LEVEL", default="INFO")
