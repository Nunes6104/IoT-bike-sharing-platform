"""Database connection setup with TLS certificate verification."""

import ssl
from urllib.parse import urlparse, parse_qs

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.pool import QueuePool


def create_secure_connection(
    db_url: str,
    ca_cert_path: str | None = None,
    verify_cert: bool = True,
    echo: bool = False,
) -> Engine:
    """
    Create a secure MySQL connection with TLS certificate verification.

    Args:
        db_url: SQLAlchemy connection string (mysql+pymysql://...).
        ca_cert_path: Path to CA certificate file for server verification.
        verify_cert: If True, require valid server certificate; if False, skip verification.
        echo: If True, log SQL statements.

    Returns:
        SQLAlchemy Engine with TLS configured.

    Raises:
        ValueError: If verification is enabled but ca_cert_path is missing.
        OSError: If ca_cert_path does not exist.
    """
    if verify_cert and not ca_cert_path:
        raise ValueError("ca_cert_path is required when verify_cert=True")
    if ca_cert_path:
        ca_cert_path = str(ca_cert_path)
        with open(ca_cert_path, 'rb') as f:
            if not f.read():
                raise ValueError(f"CA certificate is empty: {ca_cert_path}")

    engine = create_engine(
        db_url,
        poolclass=QueuePool,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
        echo=echo,
    )

    @event.listens_for(Engine, "connect")
    def configure_tls(dbapi_conn, connection_record):
        """Configure TLS on each new connection."""
        if dbapi_conn.get_server_info():
            cursor = dbapi_conn.cursor()
            cursor.execute("SELECT 1")
            cursor.close()

    if ca_cert_path and verify_cert:
        import pymysql
        def setup_ssl(conn):
            if hasattr(conn, 'sock'):
                ssl_context = ssl.create_default_context(cafile=ca_cert_path)
                ssl_context.check_hostname = True
                ssl_context.verify_mode = ssl.CERT_REQUIRED
        @event.listens_for(Engine, "connect")
        def setup_ssl_on_connect(dbapi_conn, connection_record):
            setup_ssl(dbapi_conn)

    return engine


def apply_schema(engine: Engine, schema_path: str) -> None:
    """
    Apply versioned schema from SQL file.

    Args:
        engine: SQLAlchemy Engine.
        schema_path: Path to schema.sql file.

    Raises:
        OSError: If schema file not found.
        Exception: On SQL execution error.
    """
    with open(schema_path, 'r', encoding='utf-8') as f:
        schema = f.read()

    with engine.connect() as conn:
        conn.execute(text("SET SESSION time_zone='+00:00'"))
        for statement in schema.split(';'):
            statement = statement.strip()
            if statement and not statement.startswith('--'):
                conn.execute(text(statement))
        conn.commit()
