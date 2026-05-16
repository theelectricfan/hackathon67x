"""
Direct Redshift DWH client — bypasses Redash for queries we'd rather
run against the warehouse directly (joins across im_dwh_rpt.* etc.).

Use this when:
  - the query is too heavy for Redash's polling model
  - we need streaming / large result sets
  - we want parameterised psycopg2-style binds (%s placeholders)

Otherwise prefer core.redash_client.redash.

Usage:
    from core.dwh_client import dwh
    rows = dwh.run_sql("SELECT * FROM im_dwh_rpt.dim_glusr_usr LIMIT 5")
"""
import logging
from contextlib import contextmanager
from typing import Any, Iterator

import psycopg2
from psycopg2.extras import RealDictCursor

from config.settings import settings

logger = logging.getLogger(__name__)


class DWHError(RuntimeError):
    pass


class DWHClient:
    def __init__(
        self,
        host: str | None = None,
        port: int | None = None,
        database: str | None = None,
        user: str | None = None,
        password: str | None = None,
        sslmode: str | None = None,
        connect_timeout: int | None = None,
    ):
        self.host = host or settings.DWH_HOST
        self.port = port or settings.DWH_PORT
        self.database = database or settings.DWH_DB
        self.user = user or settings.DWH_USER
        self.password = password or settings.DWH_PASSWORD
        self.sslmode = sslmode or settings.DWH_SSLMODE
        self.connect_timeout = connect_timeout or settings.DWH_CONNECT_TIMEOUT

        missing = [
            n for n, v in
            [("DWH_HOST", self.host), ("DWH_DB", self.database),
             ("DWH_USER", self.user), ("DWH_PASSWORD", self.password)]
            if not v
        ]
        if missing:
            raise DWHError(f"DWH config incomplete — missing: {', '.join(missing)}")

    @contextmanager
    def connect(self) -> Iterator[psycopg2.extensions.connection]:
        conn = psycopg2.connect(
            host=self.host,
            port=self.port,
            dbname=self.database,
            user=self.user,
            password=self.password,
            sslmode=self.sslmode,
            connect_timeout=self.connect_timeout,
        )
        try:
            yield conn
        finally:
            conn.close()

    def run_sql(
        self,
        sql: str,
        params: tuple | dict | None = None,
    ) -> list[dict[str, Any]]:
        """Execute a SELECT and return rows as list[dict]."""
        with self.connect() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(sql, params)
                return [dict(r) for r in cur.fetchall()]


dwh = DWHClient() if settings.DWH_HOST and settings.DWH_PASSWORD else None
