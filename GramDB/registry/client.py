from __future__ import annotations

import logging
from typing import Any

import aiohttp

from GramDB.config import ResolvedDatabaseUrl
from GramDB.exception import GramDBAuthError, GramDBSessionConflictError

logger = logging.getLogger("GramDB")


class RegistryClient:
    """Async HTTP client for the GramDB registry API (metadata + session lease)."""

    def __init__(self, resolved: ResolvedDatabaseUrl, *, timeout: float = 60.0) -> None:
        self._resolved = resolved
        self._timeout = aiohttp.ClientTimeout(total=timeout)

    @property
    def client_key(self) -> str:
        return self._resolved.client_key

    async def fetch_metadata(self, session: aiohttp.ClientSession) -> dict[str, Any]:
        async with session.get(self._resolved.metadata_url, timeout=self._timeout) as resp:
            if resp.status == 400:
                raise GramDBAuthError("registry rejected the database URL or client key")
            if resp.status == 404:
                raise GramDBAuthError("unknown database client key")
            if resp.status != 200:
                text = await resp.text()
                raise GramDBAuthError(f"metadata request failed ({resp.status}): {text[:500]}")
            return await resp.json()

    def _hdr(self, api_token: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {api_token}", "Content-Type": "application/json"}

    async def acquire_session(
        self,
        session: aiohttp.ClientSession,
        *,
        api_token: str,
        instance_id: str,
        client_label: str | None = None,
    ) -> None:
        url = f"{self._resolved.api_root}/sessions/acquire"
        body: dict[str, Any] = {"instance_id": instance_id}
        if client_label:
            body["client_label"] = client_label
        async with session.post(
            url, headers=self._hdr(api_token), json=body, timeout=self._timeout
        ) as resp:
            if resp.status == 409:
                data = await resp.json(content_type=None)
                raise GramDBSessionConflictError(
                    "another GramDB instance holds an active session for this database",
                    details=data if isinstance(data, dict) else None,
                )
            if resp.status not in (200, 201):
                text = await resp.text()
                raise GramDBAuthError(f"session acquire failed ({resp.status}): {text[:500]}")

    async def heartbeat(
        self,
        session: aiohttp.ClientSession,
        *,
        api_token: str,
        instance_id: str,
    ) -> None:
        url = f"{self._resolved.api_root}/sessions/heartbeat"
        async with session.post(
            url,
            headers=self._hdr(api_token),
            json={"instance_id": instance_id},
            timeout=self._timeout,
        ) as resp:
            if resp.status == 403:
                raise GramDBAuthError("heartbeat rejected (instance id mismatch or lease lost)")
            if resp.status != 200:
                text = await resp.text()
                logger.warning("heartbeat non-200: %s %s", resp.status, text[:200])

    async def release_session(
        self,
        session: aiohttp.ClientSession,
        *,
        api_token: str,
        instance_id: str,
    ) -> None:
        url = f"{self._resolved.api_root}/sessions/release"
        async with session.post(
            url,
            headers=self._hdr(api_token),
            json={"instance_id": instance_id},
            timeout=self._timeout,
        ) as resp:
            if resp.status not in (200, 204):
                text = await resp.text()
                logger.warning("session release non-success: %s %s", resp.status, text[:200])

    async def report_index_message_id(
        self,
        session: aiohttp.ClientSession,
        *,
        api_token: str,
        index_message_id: int,
    ) -> None:
        url = f"{self._resolved.api_root}/databases/index"
        async with session.post(
            url,
            headers=self._hdr(api_token),
            json={"index_message_id": index_message_id},
            timeout=self._timeout,
        ) as resp:
            if resp.status not in (200, 201):
                text = await resp.text()
                raise GramDBAuthError(f"index registration failed ({resp.status}): {text[:500]}")
