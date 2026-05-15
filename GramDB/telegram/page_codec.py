from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Page:
    current: int
    total: int
    parent_id: str
    payload: str


def encode_page(*, current: int, total: int, parent_id: str, payload: str) -> str:
    return f"GDB_PAGE:{current}:{total}:{parent_id}\n{payload}"


def decode_page(text: str) -> Page:
    head, _, rest = text.partition("\n")
    if not head.startswith("GDB_PAGE:"):
        raise ValueError("missing GDB_PAGE header")
    parts = head.split(":", 3)
    if len(parts) != 4:
        raise ValueError("invalid GDB_PAGE header")
    cur = int(parts[1])
    tot = int(parts[2])
    parent = parts[3]
    return Page(current=cur, total=tot, parent_id=parent, payload=rest)

