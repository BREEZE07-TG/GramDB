from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import TypeVar

logger = logging.getLogger("GramDB")

T = TypeVar("T")


async def run_with_flood_wait_retry(
    fn: Callable[[], Awaitable[T]],
    *,
    max_attempts: int = 8,
) -> T:
    """
    Retry on Pyrogram FloodWait with exponential slack. Re-raises other errors.
    """
    attempt = 0
    last_exc: BaseException | None = None
    while attempt < max_attempts:
        attempt += 1
        try:
            return await fn()
        except Exception as e:  # noqa: BLE001 — pyrogram raises FloodWait
            name = type(e).__name__
            if name == "FloodWait":
                wait_s = int(getattr(e, "value", 1)) + min(attempt, 5)
                logger.warning("Telegram FloodWait: sleeping %ss (attempt %s)", wait_s, attempt)
                await asyncio.sleep(wait_s)
                last_exc = e
                continue
            raise
    assert last_exc is not None
    raise last_exc
