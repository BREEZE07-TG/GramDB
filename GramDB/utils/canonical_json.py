from __future__ import annotations

import json
from typing import Any


def dumps_canonical(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"), sort_keys=True)

