import asyncio
import aiohttp
import os
import uuid
import logging
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] API-Test: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("GramDB-API-Test")

# --- CONFIGURATION ---
load_dotenv()

API_URL = os.getenv("API_BASE_URL", "http://localhost:8080")
ADMIN_TOKEN = os.getenv("GRAMDB_ADMIN_TOKEN", "")
BOT_TOKEN = os.getenv("BOT_TOKENS", "")
CLIENT_KEY = f"test_app_{uuid.uuid4().hex[:6]}"
CHANNEL_ID = -1001552477173  # Replace with a real channel ID for live tests
API_BASE_URL = API_URL + "/api/v1"

async def test_api():
    async with aiohttp.ClientSession() as session:
        logger.info(f"Starting API test against {API_BASE_URL}")

        # 1. Test Health
        async with session.get(f"{API_URL}/health") as resp:
            data = await resp.json()
            logger.info(f"Health Check: {resp.status} - {data}")

        # 2. Admin: Create Database
        logger.info(f"Creating database for client: {CLIENT_KEY}")
        if not ADMIN_TOKEN:
            logger.error("GRAMDB_ADMIN_TOKEN is required")
            return
        if not BOT_TOKEN:
            logger.error("GRAMDB_BOOTSTRAP_BOT_TOKEN is required")
            return
        headers = {"X-GramDB-Admin-Token": ADMIN_TOKEN}
        payload = {
            "client_key": CLIENT_KEY,
            "channel_id": CHANNEL_ID,
            "bot_token": BOT_TOKEN,
            "heartbeat_interval_seconds": 5
        }
        async with session.post(f"{API_BASE_URL}/admin/databases", json=payload, headers=headers) as resp:
            db_data = await resp.json()
            logger.info(f"Admin Create DB: {resp.status} - {db_data}")
            if resp.status != 201:
                logger.error("Failed to create database via admin API")
                return
            
            api_token = db_data["api_token"]
            logger.info("Note: index_message_id is expected to be null until the first GramDB client connects.")

        # 3. Get Metadata
        logger.info(f"Fetching metadata for {CLIENT_KEY}")
        async with session.get(f"{API_BASE_URL}/metadata", params={"client": CLIENT_KEY}) as resp:
            meta = await resp.json()
            logger.info(f"Metadata: {resp.status} - {meta}")

        # 4. Update Index Message ID
        logger.info("Reporting index message ID")
        auth_headers = {"Authorization": f"Bearer {api_token}"}
        payload = {"index_message_id": 123456}
        async with session.post(f"{API_BASE_URL}/databases/index", json=payload, headers=auth_headers) as resp:
            res = await resp.json()
            logger.info(f"Update Index: {resp.status} - {res}")

        # 5. Lock Database
        logger.info("Locking database")
        payload = {"reason": "Test locking mechanism"}
        async with session.post(f"{API_BASE_URL}/databases/lock", json=payload, headers=auth_headers) as resp:
            res = await resp.json()
            logger.info(f"Lock Database: {resp.status} - {res}")

        # 6. Admin: Unlock Database
        logger.info("Unlocking database")
        payload = {"client_key": CLIENT_KEY}
        async with session.post(f"{API_BASE_URL}/admin/databases/unlock", json=payload, headers=headers) as resp:
            res = await resp.json()
            logger.info(f"Unlock Database: {resp.status} - {res}")

        # 7. Session: Acquire
        instance_id = str(uuid.uuid4())
        logger.info(f"Acquiring session for instance: {instance_id}")
        payload = {"instance_id": instance_id, "client_label": "pytest-instance"}
        async with session.post(f"{API_BASE_URL}/sessions/acquire", json=payload, headers=auth_headers) as resp:
            res = await resp.json()
            logger.info(f"Acquire Session: {resp.status} - {res}")

        # 8. Session: Heartbeat
        logger.info("Sending heartbeat")
        async with session.post(f"{API_BASE_URL}/sessions/heartbeat", json={"instance_id": instance_id}, headers=auth_headers) as resp:
            res = await resp.json()
            logger.info(f"Heartbeat: {resp.status} - {res}")

        # 9. Session: Release
        logger.info("Releasing session")
        async with session.post(f"{API_BASE_URL}/sessions/release", json={"instance_id": instance_id}, headers=auth_headers) as resp:
            logger.info(f"Release Session: {resp.status}")

        logger.info("API test completed!")

if __name__ == "__main__":
    try:
        asyncio.run(test_api())
    except KeyboardInterrupt:
        pass
    except Exception as e:
        logger.exception(f"API Test failed: {e}")
