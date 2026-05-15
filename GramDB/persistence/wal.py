from __future__ import annotations

import asyncio
import json
import os
from dataclasses import asdict
from pathlib import Path
from typing import Any

from GramDB.persistence.ops import SyncOp


class WriteAheadLog:
    def __init__(self, file_path: str) -> None:
        self._path = Path(file_path)
        self._lock = asyncio.Lock()
        self._path.parent.mkdir(parents=True, exist_ok=True)

    @property
    def path(self) -> str:
        return str(self._path)

    async def append_op(self, op: SyncOp) -> None:
        line = json.dumps({"t": "op", **asdict(op)}, ensure_ascii=False, separators=(",", ":")) + "\n"
        async with self._lock:
            await asyncio.to_thread(self._append_and_fsync, line)

    async def ack(self, op_id: str, stage: str) -> None:
        line = json.dumps({"t": "ack", "op_id": op_id, "stage": stage}, ensure_ascii=False, separators=(",", ":")) + "\n"
        async with self._lock:
            await asyncio.to_thread(self._append_and_fsync, line)

    async def patch(self, op_id: str, data: dict[str, Any]) -> None:
        line = (
            json.dumps({"t": "patch", "op_id": op_id, "data": data}, ensure_ascii=False, separators=(",", ":"))
            + "\n"
        )
        async with self._lock:
            await asyncio.to_thread(self._append_and_fsync, line)

    def _append_and_fsync(self, line: str) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._path, "a", encoding="utf-8", newline="\n") as f:
            f.write(line)
            f.flush()
            os.fsync(f.fileno())

    async def load_pending(self) -> list[SyncOp]:
        async with self._lock:
            return await asyncio.to_thread(self._load_pending_sync)

    def _load_pending_sync(self) -> list[SyncOp]:
        if not self._path.exists():
            return []

        ops: dict[str, dict[str, Any]] = {}
        done: set[str] = set()
        patches: dict[str, dict[str, Any]] = {}

        with open(self._path, "r", encoding="utf-8") as f:
            for raw in f:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    rec = json.loads(raw)
                except Exception:
                    continue
                if not isinstance(rec, dict):
                    continue
                if rec.get("t") == "op":
                    op_id = rec.get("op_id")
                    if isinstance(op_id, str):
                        ops[op_id] = rec
                elif rec.get("t") == "ack":
                    if rec.get("stage") == "done":
                        op_id = rec.get("op_id")
                        if isinstance(op_id, str):
                            done.add(op_id)
                elif rec.get("t") == "patch":
                    op_id = rec.get("op_id")
                    data = rec.get("data")
                    if isinstance(op_id, str) and isinstance(data, dict):
                        cur = patches.setdefault(op_id, {})
                        cur.update(data)

        pending: list[SyncOp] = []
        for op_id, rec in ops.items():
            if op_id in done:
                continue
            try:
                payload = rec.get("payload") or {}
                if isinstance(payload, dict):
                    payload = dict(payload)
                else:
                    payload = {}
                p = patches.get(op_id)
                if isinstance(p, dict):
                    payload.update(p)
                pending.append(
                    SyncOp(
                        op_id=op_id,
                        kind=rec["kind"],
                        table=rec["table"],
                        row_uuid=rec.get("row_uuid"),
                        payload=payload,
                    )
                )
            except Exception:
                continue
        return pending
