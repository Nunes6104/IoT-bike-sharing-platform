"""Environment-backed configuration helpers for processor services."""

import os
from pathlib import Path

from sqlalchemy.engine import URL


def database_url_from_env() -> str:
    """Build a database URL from a password file without exposing it in Compose."""
    direct_url = os.environ.get("DATABASE_URL")
    if direct_url:
        return direct_url
    password_path = os.environ.get("DB_PASSWORD_FILE")
    if not password_path:
        raise ValueError("set DATABASE_URL or DB_PASSWORD_FILE")
    password_file = Path(password_path)
    password = password_file.read_text(encoding="utf-8").strip()
    if not password:
        raise ValueError(f"database password file is empty: {password_file}")
    url = URL.create(
        "mysql+pymysql",
        username=os.environ.get("DB_USER", "bike_app"),
        password=password,
        host=os.environ.get("DB_HOST", "database"),
        port=int(os.environ.get("DB_PORT", "3306")),
        database=os.environ.get("DB_NAME", "bike_sharing"),
    )
    return url.render_as_string(hide_password=False)


def mqtt_password_from_env() -> str:
    """Read the MQTT service password from a mounted secret file."""
    secret_path = os.environ.get("MQTT_PASSWORD_FILE")
    if not secret_path:
        raise ValueError("set MQTT_PASSWORD_FILE")
    password = Path(secret_path).read_text(encoding="utf-8").strip()
    if not password:
        raise ValueError(f"MQTT password file is empty: {secret_path}")
    return password
