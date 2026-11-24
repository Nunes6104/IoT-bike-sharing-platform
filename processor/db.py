"""Database connection setup with mandatory MySQL TLS identity verification."""

import re
from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.pool import QueuePool


def create_secure_connection(
    db_url: str,
    ca_cert_path: str | Path,
    echo: bool = False,
) -> Engine:
    """Create a pooled MySQL connection that requires CA and hostname verification."""
    if not db_url.startswith("mysql+pymysql://"):
        raise ValueError("the processor requires a mysql+pymysql database URL")
    ca_path = Path(ca_cert_path)
    if not ca_path.is_file() or ca_path.stat().st_size == 0:
        raise ValueError(f"CA certificate is missing or empty: {ca_path}")

    return create_engine(
        db_url,
        poolclass=QueuePool,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
        pool_recycle=1800,
        echo=echo,
        connect_args={
            # Disable FOUND_ROWS so a no-op duplicate upsert reports rowcount 0.
            "client_flag": 0,
            "ssl_ca": str(ca_path),
            "ssl_verify_cert": True,
            "ssl_verify_identity": True,
        },
    )


def apply_schema(engine: Engine, schema_path: str | Path) -> None:
    """Apply the base schema and each unapplied numbered SQL migration."""
    root = Path(schema_path)
    _execute_script(engine, root.read_text(encoding="utf-8"))

    versions = root.parent / "migrations"
    if not versions.is_dir():
        return
    for migration in sorted(versions.glob("[0-9][0-9][0-9]_*.sql")):
        version = int(migration.name[:3])
        with engine.connect() as connection:
            applied = connection.execute(
                text("SELECT 1 FROM schema_versions WHERE version = :version"),
                {"version": version},
            ).first()
        if applied:
            continue
        migration_sql = migration.read_text(encoding="utf-8")
        for index_name, table_name in re.findall(
            r"(?i)CREATE\s+UNIQUE\s+INDEX\s+([A-Za-z0-9_]+)\s+ON\s+([A-Za-z0-9_]+)",
            migration_sql,
        ):
            existing_indexes = inspect(engine).get_indexes(table_name)
            if any(index.get("name") == index_name for index in existing_indexes):
                migration_sql = re.sub(
                    rf"(?i)CREATE\s+UNIQUE\s+INDEX\s+{re.escape(index_name)}\s+ON\s+{re.escape(table_name)}\s*\([^;]+\)\s*;",
                    "",
                    migration_sql,
                )
        _execute_script(engine, migration_sql)
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO schema_versions (version, description) "
                    "VALUES (:version, :description)"
                ),
                {
                    "version": version,
                    "description": migration.stem.replace("_", " "),
                },
            )


def _execute_script(engine: Engine, script: str) -> None:
    """Execute semicolon-separated DDL after removing standalone SQL comments."""
    uncommented = re.sub(r"(?m)^\s*--.*$", "", script)
    with engine.begin() as connection:
        for statement in uncommented.split(";"):
            statement = statement.strip()
            if statement:
                connection.execute(text(statement))
        if engine.dialect.name == "mysql":
            connection.execute(text("SET SESSION time_zone='+00:00'"))
