# GramDB: Telegram-Backed Distributed NoSQL Database

GramDB is a robust, asynchronous Python database library that uses Telegram channels as a persistent storage backend. It combines the ease of use of a NoSQL database with the massive, free storage capacity of Telegram, while maintaining high performance through an in-memory cache and a registry-based session management system.

[![PyPI version](https://badge.fury.io/py/gramdb.svg)](https://badge.fury.io/py/gramdb)
[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)

## 🚀 Features

- **Infinite Cold Storage**: Use private Telegram channels to store gigabytes of data for free.
- **High Performance**: Reads and complex queries are served from an in-memory "hot cache".
- **Reliability**: Built-in Write-Ahead Log (WAL) ensures your data isn't lost during crashes.
- **Concurrency Control**: A Registry API manages session leases to prevent multiple writers from corrupting the index.
- **Anti-Flood Rotation**: A pool of bot workers automatically rotates tokens to avoid Telegram's API flood limits.
- **Easy Integration**: Simple MongoDB-like API (`find`, `insert`, `update`, `delete`).

## 🛠 Architecture

- **Client Library (`GramDB`)**: The core logic that runs in your application.
- **Registry API**: A central service that manages database metadata and sessions.
- **Storage Backend**: A private Telegram channel where your data lives.

## 📦 Installation

You can install the package directly from PyPI:

```bash
pip install gramdb
```

## 🚦 Quick Start

### 1. Setup the Registry API
Ensure you have db url from gramdb

### 2. Connect the Client
```python
import asyncio
from GramDB import GramDB

async def main():
    # Registry URL and your bot tokens
    DB_URL = "http://gramdb/api/v1?client=my_app"

    # Get bot token from t.me/botfather
    BOT_TOKENS = ["token1", "token2"]

    # Get api id and hash from my.telegram.org
    API_ID=12345678
    API_HASH="987654321qwerty"

    async with GramDB(DB_URL, BOT_TOKENS, api_id=API_ID, api_hash=API_HASH) as db:
        # Insert a record
        await db.insert_one("users", {"name": "Alice", "age": 25})
        
        # Query records
        users = await db.find("users", {"name": "Alice"})
        print(users)

asyncio.run(main())
```

## 🤝 Contributing

We welcome contributions! Please see our [CONTRIBUTING.md](CONTRIBUTING.md) for details on how to submit pull requests and our [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) for our standards of behavior.

### PR Requirements:
- Follow PEP 8 coding standards.
- Add docstrings to all new functions and classes.
- Ensure all tests pass.
- Provide a clear description of your changes.

## 👨‍💻 Author & Support

Created and managed by **[ishikki akabane](https://github.com/ishikki-akabane)**.

- **Telegram Support Group**: [t.me/gramdbsupport](https://t.me/gramdbsupport)
- **Telegram Update Channel**: [t.me/gramdb](https://t.me/gramdb)

## 📜 License

This project is licensed under the GNU License - see the [LICENSE](LICENSE) file for details.

---

Built with ❤️ by [ishikki-akabane](https://github.com/ishikki-akabane) and the GramDB Community.
