import asyncio
import logging
import os
import statistics
import time
import uuid

import aiohttp
from dotenv import load_dotenv

from GramDB import GramDB
from GramDB.config import parse_database_url

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("GramDB-Test")

# --- CONFIGURATION ---
# Replace these with your live credentials or set them in environment variables
load_dotenv()

DATABASE_URL = os.getenv(
    "GRAMDB_URL",
    "http://localhost:8080/api/v1/metadata?client=test"
)
BOT_TOKENS = os.getenv("BOT_TOKENS", "TOKEN1").split(",")
API_ID = os.getenv("API_ID", 123456789)
API_HASH = os.getenv("API_HASH", "111222333aaabbbccddd")


def _ms(t0: float, t1: float) -> float:
    return (t1 - t0) * 1000.0


async def _timed(label: str, coro):  # noqa: ANN001
    t0 = time.perf_counter()
    out = await coro
    t1 = time.perf_counter()
    logger.info("%s: %.2f ms", label, _ms(t0, t1))
    return out


async def _benchmark_find_one(db: GramDB, table_name: str, record_id: str, *, rounds: int) -> None:
    durs: list[float] = []
    for _ in range(rounds):
        t0 = time.perf_counter()
        await db.find_one(table_name, {"_id": record_id})
        durs.append(_ms(t0, time.perf_counter()))

    durs.sort()
    avg = statistics.fmean(durs) if durs else 0.0
    p50 = durs[int(0.50 * (len(durs) - 1))] if durs else 0.0
    p95 = durs[int(0.95 * (len(durs) - 1))] if durs else 0.0
    logger.info("Algorithm benchmark (find_one x%d): avg=%.3f ms p50=%.3f ms p95=%.3f ms", rounds, avg, p50, p95)


async def _benchmark_registry_metadata(url: str, *, rounds: int) -> dict:
    durs: list[float] = []
    last: dict = {}
    timeout = aiohttp.ClientTimeout(total=15)
    async with aiohttp.ClientSession(timeout=timeout) as s:
        for _ in range(rounds):
            t0 = time.perf_counter()
            async with s.get(url) as resp:
                data = await resp.json(content_type=None)
            durs.append(_ms(t0, time.perf_counter()))
            if isinstance(data, dict):
                last = data

    durs.sort()
    avg = statistics.fmean(durs) if durs else 0.0
    p50 = durs[int(0.50 * (len(durs) - 1))] if durs else 0.0
    p95 = durs[int(0.95 * (len(durs) - 1))] if durs else 0.0
    logger.info("API benchmark (GET /metadata x%d): avg=%.2f ms p50=%.2f ms p95=%.2f ms", rounds, avg, p50, p95)
    return last


async def run_crud_test():
    """
    Performs a full CRUD cycle on GramDB.
    """
    logger.info("Starting GramDB CRUD test...")

    resolved = parse_database_url(DATABASE_URL)
    await _benchmark_registry_metadata(resolved.metadata_url, rounds=int(os.getenv("GRAMDB_TEST_API_ROUNDS", "5")))

    table_name = os.getenv("GRAMDB_TEST_TABLE", "test_table")
    schema = ("_id", "name", "age", "status")
    persistent_id = os.getenv("GRAMDB_TEST_PERSISTENT_ID", "user_123")
    cleanup = os.getenv("GRAMDB_TEST_CLEANUP", "0").lower() in ("1", "true", "yes", "y")

    db = GramDB(DATABASE_URL, BOT_TOKENS, int(API_ID), str(API_HASH))
    t0 = time.perf_counter()
    await db.connect(client_label="crud-speed-test")
    logger.info("GramDB connect (total): %.2f ms", _ms(t0, time.perf_counter()))
    try:
        exists = await _timed(f"check_table({table_name})", db.check_table(table_name))
        if not exists:
            await _timed(f"create_one({table_name})", db.create_one(table_name, schema))

        found = await _timed(f"find_one(_id={persistent_id})", db.find_one(table_name, {"_id": persistent_id}))
        if not found:
            record = {"_id": persistent_id, "name": "Alice", "age": 30, "status": "active"}
            await _timed("insert_one(persistent)", db.insert_one(table_name, record))
            found = await _timed("find_one(persistent after insert)", db.find_one(table_name, {"_id": persistent_id}))

        if not found or found.get("name") != "Alice":
            raise RuntimeError("Persistent record missing or data mismatch after insert/load")

        cur_age = int(found.get("age") or 0)
        await _timed("update_one(persistent age+1)", db.update_one(table_name, {"_id": persistent_id}, {"$set": {"age": cur_age + 1}}))
        updated = await _timed("find_one(persistent after update)", db.find_one(table_name, {"_id": persistent_id}))
        if not updated or int(updated.get("age") or 0) != cur_age + 1:
            raise RuntimeError("Update failed")

        run_id = f"run_{uuid.uuid4().hex[:10]}"
        run_record = {"_id": run_id, "name": "RunUser", "age": 1, "status": "run"}
        await _timed("insert_one(run)", db.insert_one(table_name, run_record))

        all_records = await _timed("find_all(table)", db.find_all(table_name))
        logger.info("Loaded records in '%s': %d", table_name, len(all_records))

        await _benchmark_find_one(
            db,
            table_name,
            persistent_id,
            rounds=int(os.getenv("GRAMDB_TEST_ALGO_ROUNDS", "200")),
        )

        if cleanup:
            await _timed("delete_one(run)", db.delete_one(table_name, {"_id": run_id}))
    finally:
        await db.close()

    logger.info("GramDB test completed successfully (data preserved).")

if __name__ == "__main__":
    try:
        asyncio.run(run_crud_test())
    except KeyboardInterrupt:
        pass
    except Exception as e:
        logger.exception(f"Test failed with error: {e}")
