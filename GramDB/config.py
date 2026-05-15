from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath
from urllib.parse import parse_qs, urlsplit, unquote


@dataclass(frozen=True)
class ResolvedDatabaseUrl:
    """
    Parsed database URL pointing at the GramDB registry metadata endpoint.

    Example:
        https://api.example.com/api/v1/metadata?client=myapp@69696969.gramdb
    """

    metadata_url: str
    client_key: str

    @property
    def api_root(self) -> str:
        """
        Base URL for sibling routes (sessions, index reporting) under the same
        parent path as ``metadata``. For path ``/api/v1/metadata`` the root is
        ``https://host/api/v1``.
        """
        sp = urlsplit(self.metadata_url)
        parent = str(PurePosixPath(sp.path).parent)
        if parent in ("", ".", "/"):
            parent = "/api/v1"
        return f"{sp.scheme}://{sp.netloc}{parent}"


def parse_database_url(db_url: str) -> ResolvedDatabaseUrl:
    sp = urlsplit(db_url.strip())
    qs = parse_qs(sp.query)
    raw = qs.get("client") or qs.get("Client")
    if not raw or not raw[0]:
        raise ValueError(
            "database URL must include a non-empty client query parameter, "
            "for example: https://host/api/v1/metadata?client=myapp@uuid.gramdb"
        )
    return ResolvedDatabaseUrl(metadata_url=db_url.strip(), client_key=unquote(raw[0]))
