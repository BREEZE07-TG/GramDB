from __future__ import annotations

import json
from typing import Any


def dumps_compact(obj: Any) -> str:
    return json.dumps(obj, separators=(",", ":"), ensure_ascii=False)


def loads_safe(s: str) -> Any:
    return json.loads(s)
