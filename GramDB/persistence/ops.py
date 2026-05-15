from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal


OpKind = Literal[
    "table_create",
    "table_drop",
    "row_upsert",
    "row_delete",
]


@dataclass(frozen=True)
class SyncOp:
    op_id: str
    kind: OpKind
    table: str
    row_uuid: str | None
    payload: dict[str, Any]

