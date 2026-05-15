# GramDB

GramDB is a small **async-only** Python library that uses a **private Telegram channel** as durable storage for JSON rows, while keeping **hot read/write paths in plain Python dicts** (table-oriented query helpers). A separate **Quart + MongoDB registry API** hands out channel metadata and enforces **one live client per database** using heartbeats.

## Why this shape

- **Telegram** gives you effectively unbounded append-only storage for small JSON payloads (with practical limits per message; the client automatically switches to small **document** messages when a row exceeds the safe text size).
- **In-process dict indexes** keep queries fast once the channel has been hydrated.
- **Multiple bot tokens** rotate per Telegram call so you share flood limits across workers. **Every bot must be a channel admin** with permission to post (and delete, for row deletes).
- **Single session**: the registry API issues a lease; a second `GramDB.connect()` for the same database receives **409** and the library raises `GramDBSessionConflictError`.

## Install

```bash
pip install -e .
# Optional (faster crypto for Pyrogram):
# pip install tgcrypto
```

Python **3.10+** is required.

## Registry API (separate service)

The HTTP service lives under `api/` and is **not** installed with the `GramDB` package. See [`api/README.md`](api/README.md) for environment variables, admin provisioning, and how to run it with Quart.

## Database URL

Pass the **full metadata URL** you get from hosting the registry, including the `client` query string (same pattern as older GramDB releases):

```text
https://your-host.example.com/api/v1/metadata?client=myapp@69696969.gramdb
```

The legacy path `/api/v1/database?client=...` is also supported by the reference API.

The client derives sibling endpoints (sessions, index registration) from the parent path of that URL (`…/api/v1`).

## Minimal usage

```python
import asyncio
from GramDB import GramDB, GramDBSessionConflictError

DATABASE_URL = "https://your-host/api/v1/metadata?client=myapp@69696969.gramdb"
BOT_TOKENS = ["123456:AAA...", "123456:BBB..."]  # two or more recommended

async def main():
    db = GramDB(DATABASE_URL, BOT_TOKENS)
    try:
        await db.connect(client_label="worker-1")
    except GramDBSessionConflictError as exc:
        print("Another process already connected:", exc.details)
        return

    if not await db.check_table("users"):
        await db.create_one("users", ["_id", "name"])

    await db.insert_one("users", {"_id": 1, "name": "Ada"})
    row = await db.find_one("users", {"_id": 1})
    print(row)

    await db.close()

asyncio.run(main())
```

Context manager form:

```python
async with GramDB(DATABASE_URL, BOT_TOKENS) as db:
    ...
```

## Operations

| Method | Purpose |
|--------|---------|
| `connect` / `close` | Acquire registry lease, start Pyrogram pool, hydrate cache, start heartbeats |
| `check_table` | Whether a table exists |
| `create_one` (`create`) | Create table + placeholder row (matches legacy behaviour) |
| `insert_one` (`insert`) | Insert row (Telegram send + index update) |
| `find` (`fetch`) | Query rows (dict operators supported by the engine) |
| `find_one` | First match |
| `find_all` | All rows (optional per-table) |
| `update_one` (`update`) | Operator updates (`$set`, `$inc`, …) then Telegram edit |
| `delete_one` (`delete`) | Remove row locally and delete Telegram message |
| `delete_table` | Drop table, delete backing messages, rewrite index |

`wait_for_background_tasks()` is a no-op compatibility hook; persistence is awaited inline.

## Package layout

```text
GramDB/
  client.py          # async GramDB façade
  config.py          # database URL parsing
  registry/client.py # aiohttp calls to the registry
  telegram/          # Pyrogram worker pool + channel persistence
  engine/query.py    # in-memory dict engine (EfficientDictQuery)
  utils/             # JSON helpers, Telegram payload sizing, flood retries
  exception.py       # typed errors
api/                 # Quart + MongoDB registry (separate deployable)
```

## Limitations (and how they are handled)

| Limit | Mitigation |
|-------|------------|
| Telegram message size | Rows larger than the safe text window are stored as **documents** with a small header marker |
| Flood limits | Multiple bot tokens, per-call worker rotation, automatic `FloodWait` backoff |
| Index message size | The catalog is one JSON message; extremely wide databases may hit the index size ceiling—archive old tables or split logical databases |
| Crash mid-write | Channel + index updates are ordered defensively; worst case leaves orphan Telegram messages—manual cleanup is possible |

## License

GPL-3.0 (see `LICENSE`).
