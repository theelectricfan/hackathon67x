"""
Redash client — replaces CSV ingestion.

Two execution paths:
  - run_sql(sql, data_source_id, ...)  → ad-hoc SQL on a data source
  - run_saved(query_id, parameters)    → saved Redash query by id

Both return a list[dict] of rows (column-name keyed) and handle async
polling transparently. Pair with pandas.DataFrame(rows) when you need
the tabular shape the old context builder expected.
"""
import logging
import time
from typing import Any

import httpx

from config.settings import settings

logger = logging.getLogger(__name__)


class RedashError(RuntimeError):
    pass


class RedashClient:
    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        poll_interval: float | None = None,
        timeout: int | None = None,
    ):
        self.base_url = (base_url or settings.REDASH_URL or "").rstrip("/")
        self.api_key = api_key or settings.REDASH_API_KEY
        self.poll_interval = poll_interval or settings.REDASH_POLL_INTERVAL
        self.timeout = timeout or settings.REDASH_QUERY_TIMEOUT

        if not self.base_url:
            raise RedashError("REDASH_URL is not configured")
        if not self.api_key:
            raise RedashError("REDASH_API_KEY is not configured")

        self._headers = {
            "Authorization": f"Key {self.api_key}",
            "Content-Type": "application/json",
        }

    # ── Public API ──────────────────────────────────────────────────────────

    def run_sql(
        self,
        sql: str,
        data_source_id: int,
        max_age: int = 0,
    ) -> list[dict[str, Any]]:
        """
        Execute ad-hoc SQL on a data source. Returns rows as list of dicts.
        max_age=0 forces a fresh run; pass a positive int to accept cached
        results younger than that many seconds.
        """
        payload = {"data_source_id": data_source_id, "query": sql, "max_age": max_age}
        body = self._post("/api/query_results", payload)
        return self._resolve_body(body)

    def run_saved(
        self,
        query_id: int,
        parameters: dict[str, Any] | None = None,
        max_age: int = 0,
    ) -> list[dict[str, Any]]:
        """
        Execute a saved Redash query by id, optionally with parameters.
        """
        payload = {"parameters": parameters or {}, "max_age": max_age}
        body = self._post(f"/api/queries/{query_id}/results", payload)
        return self._resolve_body(body)

    # ── Internals ───────────────────────────────────────────────────────────

    def _resolve_body(self, body: dict) -> list[dict[str, Any]]:
        """Either a direct query_result (cached) or a job to poll."""
        if "query_result" in body:
            return body["query_result"]["data"]["rows"]
        if "job" in body:
            return self._poll_job(body["job"]["id"])
        raise RedashError(f"unexpected Redash response: keys={list(body)}")

    def _poll_job(self, job_id: str) -> list[dict[str, Any]]:
        deadline = time.time() + self.timeout
        while time.time() < deadline:
            job = self._get(f"/api/jobs/{job_id}")["job"]
            status = job.get("status")
            # Redash job status: 1=pending, 2=started, 3=success, 4=failure, 5=cancelled
            if status == 3:
                qrid = job.get("query_result_id") or job.get("result")
                if not qrid:
                    raise RedashError("job succeeded but no query_result_id")
                return self._fetch_result(qrid)
            if status in (4, 5):
                raise RedashError(f"Redash job {job_id} failed: {job.get('error')!r}")
            time.sleep(self.poll_interval)
        raise RedashError(f"Redash job {job_id} exceeded {self.timeout}s timeout")

    def _fetch_result(self, query_result_id: int) -> list[dict[str, Any]]:
        body = self._get(f"/api/query_results/{query_result_id}")
        return body["query_result"]["data"]["rows"]

    def _post(self, path: str, payload: dict) -> dict:
        url = f"{self.base_url}{path}"
        with httpx.Client(timeout=30.0) as c:
            r = c.post(url, headers=self._headers, json=payload)
        if r.status_code >= 400:
            raise RedashError(f"POST {path} → {r.status_code} {r.text[:300]}")
        return r.json()

    def _get(self, path: str) -> dict:
        url = f"{self.base_url}{path}"
        with httpx.Client(timeout=30.0) as c:
            r = c.get(url, headers=self._headers)
        if r.status_code >= 400:
            raise RedashError(f"GET {path} → {r.status_code} {r.text[:300]}")
        return r.json()


# Singleton — mirrors the llm singleton pattern in llm/client.py
redash = RedashClient() if settings.REDASH_API_KEY else None
