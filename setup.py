from setuptools import find_packages, setup

import re

requirements = [
    "aiohttp>=3.9.0",
    "pyrogram>=2.0.106",
]

readme = ""
with open("README.md", encoding="utf-8") as f:
    readme = f.read()

with open("GramDB/__init__.py", encoding="utf-8") as f:
    version = re.findall(r'__version__ = "(.+)"', f.read())[0]

setup(
    name="GramDB",
    author="ishikki-Akabane",
    author_email="ishikkiakabane@outlook.com",
    version=version,
    long_description=readme,
    long_description_content_type="text/markdown",
    url="https://github.com/ishikki-akabane/GramDB",
    download_url="https://github.com/ishikki-akabane/GramDB/releases/latest",
    license="GNU General Public License v3.0",
    classifiers=[
        "Framework :: AsyncIO",
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: GNU General Public License v2 or later (GPLv2+)",
        "Natural Language :: English",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Internet :: WWW/HTTP",
        "Topic :: Software Development :: Libraries",
    ],
    description="Telegram-backed JSON database with in-memory dict speed and a registry API.",
    include_package_data=True,
    keywords=["telegram", "db", "database", "asyncio", "pyrogram", "storage"],
    packages=find_packages(include=["GramDB", "GramDB.*"]),
    install_requires=requirements,
    python_requires=">=3.10",
)
