from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any

import aiohttp

from GramDB.config import parse_database_url
from GramDB.engine.query import EfficientDictQuery
from GramDB.exception import GramDBError, GramDBTelegramError
from GramDB.registry.client import RegistryClient
from GramDB.telegram.channel_store import TelegramChannelStore
from GramDB.telegram.pyrogram_pool import PyrogramWorkerPool

logger = logging.getLogger("GramDB")


class GramDB:
    """
    Async GramDB client: metadata and session lease from the registry API, row
    storage in a private Telegram channel via Pyrogram (rotating bot workers).
    """

    def __init__(
        self,
        database_url: str,
        bot_tokens: str | list[str],
        api_id: int, api_hash: str,
        *,
        http_session: aiohttp.ClientSession | None = None,
    ) -> None:
        if isinstance(bot_tokens, str):
            bot_tokens = [bot_tokens]
        self._database_url = database_url.strip()
        self._bot_tokens = list(bot_tokens)
        self._api_id = api_id
        self._api_hash = api_hash
        self._http_external = http_session is not None
        self._http = http_session
        self._resolved = parse_database_url(self._database_url)
        self._registry = RegistryClient(self._resolved)

        self._pool: PyrogramWorkerPool | None = None
        self._store: TelegramChannelStore | None = None
        self._engine: EfficientDictQuery | None = None
        self._metadata: dict[str, Any] = {}

        self._instance_id = str(uuid.uuid4())
        self._heartbeat_task: asyncio.Task[None] | None = None
        self._connected = False
        self._write_lock = asyncio.Lock()

        if len(self._bot_tokens) < 2:
            logger.warning(
                "Using fewer than two bot tokens increases flood-wait risk; "
                "add every bot as channel admin and pass at least two tokens."
            )

    @property
    def connected(self) -> bool:
        return self._connected

    async def connect(self, *, client_label: str | None = None) -> None:
        if self._connected:
            raise GramDBError("GramDB client is already connected")

        if self._http is None:
            self._http = aiohttp.ClientSession()

        lease_acquired = False
        api_token: str | None = None
        try:
            meta = await self._registry.fetch_metadata(self._http)
            self._metadata = meta

            token = meta.get("api_token")
            if not token or not isinstance(token, str):
                raise GramDBError("registry metadata missing api_token")
            api_token = token

            channel_id = meta.get("channel_id")
            if channel_id is None:
                raise GramDBError("registry metadata missing channel_id")
            channel_id = int(channel_id)

            index_message_id = meta.get("index_message_id")
            if index_message_id is not None:
                index_message_id = int(index_message_id)
                if index_message_id <= 0:
                    index_message_id = None

            hb = float(meta.get("heartbeat_interval_seconds", 15))

            await self._registry.acquire_session(
                self._http,
                api_token=api_token,
                instance_id=self._instance_id,
                client_label=client_label,
            )
            lease_acquired = True

            self._pool = PyrogramWorkerPool(self._bot_tokens, self._api_id, self._api_hash)
            await self._pool.start()
            await self._pool.ensure_channel_admin(channel_id)

            self._store = TelegramChannelStore(self._pool, channel_id, index_message_id)

            if index_message_id is None:
                empty = TelegramChannelStore.empty_index()
                new_mid = await self._store.send_index(empty)
                self._store.index_message_id = new_mid
                await self._registry.report_index_message_id(
                    self._http, api_token=api_token, index_message_id=new_mid
                )
                logger.info("Bootstrapped new GramDB index message id=%s", new_mid)

            await self._hydrate_engine()

            self._heartbeat_task = asyncio.create_task(
                self._heartbeat_loop(api_token=api_token, interval=hb),
                name="gramdb-heartbeat",
            )
            self._connected = True
            logger.info("GramDB connected (%s)", self._resolved.client_key)
        except Exception:
            if lease_acquired and self._http and api_token:
                try:
                    await self._registry.release_session(
                        self._http,
                        api_token=api_token,
                        instance_id=self._instance_id,
                    )
                except Exception:  # noqa: BLE001
                    logger.exception("failed to release session after partial connect")
            if self._pool:
                await self._pool.stop()
                self._pool = None
            self._store = None
            self._engine = None
            if self._http and not self._http_external:
                await self._http.close()
                self._http = None
            raise

    async def _heartbeat_loop(self, *, api_token: str, interval: float) -> None:
        try:
            while True:
                await asyncio.sleep(max(3.0, interval))
                if not self._http:
                    break
                await self._registry.heartbeat(
                    self._http,
                    api_token=api_token,
                    instance_id=self._instance_id,
                )
        except asyncio.CancelledError:
            return
        except Exception:  # noqa: BLE001
            logger.exception("heartbeat loop crashed")

    async def _hydrate_engine(self) -> None:
        assert self._store is not None
        index = await self._store.read_index_dict()
        tables = index.get("tables") or {}
        all_ids: list[int] = []
        for _t, mids in tables.items():
            if not isinstance(mids, list):
                continue
            for mid in mids:
                try:
                    all_ids.append(int(mid))
                except (TypeError, ValueError):
                    continue

        rows: dict[str, dict[str, Any]] = {}
        messages = await self._store.fetch_messages(all_ids)
        for msg in messages:
            if not msg or getattr(msg, "empty", False):
                continue
            try:
                row = await self._store.parse_row_message(msg)
            except Exception:  # noqa: BLE001
                logger.warning("skipping unreadable message id=%s", getattr(msg, "id", "?"))
                continue
            mid = str(msg.id)
            row["_m_id"] = mid
            rows[mid] = row

        self._engine = EfficientDictQuery(rows)

    async def _reload_engine_from_channel(self) -> None:
        await self._hydrate_engine()

    def _require_engine(self) -> EfficientDictQuery:
        if not self._engine:
            raise GramDBError("GramDB is not connected")
        return self._engine

    async def close(self) -> None:
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
            self._heartbeat_task = None

        api_token = self._metadata.get("api_token") if isinstance(self._metadata, dict) else None
        if self._http and api_token:
            try:
                await self._registry.release_session(
                    self._http,
                    api_token=str(api_token),
                    instance_id=self._instance_id,
                )
            except Exception:  # noqa: BLE001
                logger.exception("session release failed")

        if self._pool:
            await self._pool.stop()
            self._pool = None

        if self._http and not self._http_external:
            await self._http.close()
            self._http = None
        self._store = None
        self._engine = None
        self._connected = False
        logger.info("GramDB closed")

    async def __aenter__(self) -> GramDB:
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:  # noqa: ANN001
        await self.close()

    # --- CRUD (aliases match older GramDB examples) ---

    async def check_table(self, table_name: str) -> bool:
        return await self._require_engine().check_table(table_name)

    async def create_one(self, table_name: str, schema: list[str] | tuple[str, ...]) -> None:
        async with self._write_lock:
            eng = self._require_engine()
            assert self._store is not None
            sample_record: dict[str, Any] = {field: "gramdb" for field in schema}
            sample_record["_id"] = "sample1928"
            sample_record["_table_"] = table_name
            mid = await self._store.send_row(sample_record)

            def mut(idx: dict[str, Any]) -> None:
                tables = idx.setdefault("tables", {})
                if table_name in tables:
                    raise ValueError(f"Table '{table_name}' already exists.")
                tables[table_name] = [mid]

            await self._mutate_index(mut)
            sample_record["_m_id"] = str(mid)
            if "_table_" in sample_record:
                del sample_record["_table_"]
            await eng.create(table_name, schema, sample_record, str(mid))

    async def insert_one(self, table_name: str, record: dict[str, Any]) -> None:
        async with self._write_lock:
            eng = self._require_engine()
            assert self._store is not None
            rec = dict(record)
            if "_id" not in rec:
                rec["_id"] = await eng._generate_random_id()  # noqa: SLF001
            rec["_table_"] = table_name
            mid = await self._store.send_row(rec)

            def mut(idx: dict[str, Any]) -> None:
                tables = idx.setdefault("tables", {})
                lst = tables.setdefault(table_name, [])
                lst.append(mid)

            await self._mutate_index(mut)
            rec["_m_id"] = str(mid)
            rec.pop("_table_", None)
            await eng.insert_one(table_name, rec, _m_id=str(mid))

    async def find(self, table_name: str, query: dict[str, Any]) -> list[dict[str, Any]]:
        return await self._require_engine().fetch(table_name, query)

    async def find_one(self, table_name: str, query: dict[str, Any]) -> dict[str, Any] | None:
        rows = await self.find(table_name, query)
        return rows[0] if rows else None

    async def find_all(self, table: str | None = None) -> Any:
        return await self._require_engine().fetch_all(table)

    async def update_one(
        self, table_name: str, query: dict[str, Any], update_query: dict[str, Any]
    ) -> None:
        async with self._write_lock:
            eng = self._require_engine()
            assert self._store is not None
            old_m_id, _old_id = await eng.update_one(table_name, query, update_query)
            rows = await eng.fetch(table_name, {"_id": _old_id})
            if not rows:
                raise GramDBError("failed to read row after update")
            row = dict(rows[0])
            tg_body = dict(row)
            tg_body["_table_"] = table_name
            new_mid = await self._store.edit_row(int(old_m_id), tg_body)
            if str(new_mid) != str(old_m_id):

                def mut(idx: dict[str, Any]) -> None:
                    lst = idx.get("tables", {}).get(table_name)
                    if not isinstance(lst, list):
                        return
                    for i, v in enumerate(lst):
                        if int(v) == int(old_m_id):
                            lst[i] = new_mid
                            break

                await self._mutate_index(mut)
                await self._reload_engine_from_channel()

    async def delete_one(self, table_name: str, query: dict[str, Any]) -> None:
        async with self._write_lock:
            eng = self._require_engine()
            assert self._store is not None
            rows = await eng.fetch(table_name, query)
            if not rows:
                raise ValueError(f"No records found matching query: {query}")
            m_id = rows[0]["_m_id"]
            await self._store.delete_row_message(int(m_id))

            def mut(idx: dict[str, Any]) -> None:
                lst = idx.get("tables", {}).get(table_name)
                if not isinstance(lst, list):
                    return
                idx["tables"][table_name] = [x for x in lst if int(x) != int(m_id)]

            await self._mutate_index(mut)
            try:
                await eng.delete_one(table_name, query)
            except Exception:
                await self._reload_engine_from_channel()
                raise

    async def delete_table(self, table_name: str) -> None:
        async with self._write_lock:
            eng = self._require_engine()
            assert self._store is not None
            index = await self._store.read_index_dict()
            mids = list(index.get("tables", {}).get(table_name) or [])
            if not isinstance(mids, list):
                mids = []

            for mid in mids:
                try:
                    await self._store.delete_row_message(int(mid))
                except Exception:  # noqa: BLE001
                    logger.warning("failed deleting telegram message %s", mid)

            def mut(idx: dict[str, Any]) -> None:
                if table_name in idx.get("tables", {}):
                    del idx["tables"][table_name]

            await self._mutate_index(mut)
            await eng.delete_table(table_name)

    async def _mutate_index(self, mutator) -> None:  # noqa: ANN001
        assert self._store is not None
        idx = await self._store.read_index_dict()
        mutator(idx)
        await self._store.write_index_dict(idx)

    async def wait_for_background_tasks(self) -> None:
        """Compatibility hook; persistence is awaited inline in this version."""

        return

    # --- legacy names used in older scripts ---

    create = create_one
    insert = insert_one
    fetch = find
    update = update_one
    delete = delete_one

    @staticmethod
    async def create_client(
        database_url: str,
        bot_tokens: str | list[str],
        *,
        client_label: str | None = None,
        http_session: aiohttp.ClientSession | None = None,
    ) -> GramDB:
        g = GramDB(database_url, bot_tokens, http_session=http_session)
        await g.connect(client_label=client_label)
        return g
