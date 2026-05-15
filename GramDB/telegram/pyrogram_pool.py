from __future__ import annotations

import asyncio
import hashlib
import logging
import tempfile
from collections.abc import Awaitable, Callable
from typing import TypeVar

from pyrogram import Client
from pyrogram.enums import ChatMemberStatus

from GramDB.exception import GramDBTelegramError
from GramDB.utils.retry import run_with_flood_wait_retry

logger = logging.getLogger("GramDB")

T = TypeVar("T")


def _token_fp(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()[:10]


class PyrogramWorkerPool:
    """
    One Pyrogram bot client per token. ``execute`` picks workers in round-robin
    order so load spreads across tokens (flood-limit friendly).
    """

    def __init__(self, bot_tokens: list[str], api_id: int, api_hash: str) -> None:
        if not bot_tokens:
            raise ValueError("Provide at least one bot token (two or more are recommended).")
        
        self._api_id = api_id
        self._api_hash = api_hash
        self._tokens = list(dict.fromkeys(bot_tokens))
        self._clients: list[Client] = []
        self._rr = 0
        self._lock = asyncio.Lock()
        self._started = False

    async def start(self) -> None:
        if self._started:
            return
        async with self._lock:
            if self._started:
                return
            for i, token in enumerate(self._tokens):
                session = f"gramdb_{i}_{_token_fp(token)}"
                workdir = tempfile.mkdtemp(prefix="gramdb_session_")
                client = Client(
                    session,
                    bot_token=token,
                    api_id=self._api_id, api_hash=self._api_hash,
                    workdir=workdir, no_updates=True
                )
                await client.start()
                self._clients.append(client)
                logger.info("Started Pyrogram worker %s (session dir %s)", i, workdir)
            self._started = True

    async def stop(self) -> None:
        for c in self._clients:
            try:
                await c.stop()
            except Exception:  # noqa: BLE001
                logger.exception("error stopping pyrogram client")
        self._clients.clear()
        self._started = False

    def _next_client(self) -> Client:
        c = self._clients[self._rr % len(self._clients)]
        self._rr += 1
        return c

    async def execute(self, fn: Callable[[Client], Awaitable[T]]) -> T:
        if not self._clients:
            raise RuntimeError("PyrogramWorkerPool is not started")
        client = self._next_client()

        async def once() -> T:
            return await fn(client)

        return await run_with_flood_wait_retry(once)

    async def ensure_channel_admin(self, channel_id: int) -> None:
        """
        Every worker bot must be able to post in the channel. Raises if any bot
        lacks administrator privileges with posting rights.
        """

        async def check_one(client: Client) -> None:
            me = await client.get_me()
            member = await client.get_chat_member(channel_id, me.id)
            ok = False
            if member.status == ChatMemberStatus.OWNER:
                ok = True
            elif member.status == ChatMemberStatus.ADMINISTRATOR:
                priv = member.privileges
                if priv is not None and getattr(priv, "can_post_messages", False):
                    ok = True
                elif priv is not None and getattr(priv, "can_manage_chat", False):
                    ok = True
            if not ok:
                raise GramDBTelegramError(
                    f"bot @{getattr(me, 'username', None) or me.id} is not a channel admin "
                    "with can_post_messages (add every bot token as administrator)."
                )

        for c in self._clients:
            await check_one(c)
