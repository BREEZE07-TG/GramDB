from __future__ import annotations

import json
from typing import Any

from GramDB.utils.json_codec import dumps_compact, loads_safe

# Telegram message hard limit is 4096; leave margin for edits and UTF-8 expansion.
MAX_SAFE_MESSAGE_BYTES = 3800

_ROW_DOC_MARKER = "GRAMDB_ROW_JSON\n"


def row_to_channel_payload(row: dict[str, Any]) -> tuple[str | None, bytes | None]:
    """
    Returns (text, document_bytes). Exactly one is non-None.
    Large rows are sent as UTF-8 JSON documents.
    """
    text = dumps_compact(row)
    if len(text.encode("utf-8")) <= MAX_SAFE_MESSAGE_BYTES:
        return text, None
    return None, text.encode("utf-8")


def parse_row_message(*, text: str | None, document_bytes: bytes | None) -> dict[str, Any]:
    if document_bytes is not None:
        raw = document_bytes.decode("utf-8")
        if raw.startswith(_ROW_DOC_MARKER):
            raw = raw[len(_ROW_DOC_MARKER) :]
        return loads_safe(raw)
    if text is None:
        raise ValueError("empty GramDB row message")
    return loads_safe(text)


def wrap_document_body(body: bytes) -> bytes:
    return (_ROW_DOC_MARKER).encode("utf-8") + body
