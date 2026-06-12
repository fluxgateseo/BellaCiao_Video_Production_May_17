from __future__ import annotations

import socket
from functools import lru_cache


@lru_cache(maxsize=32)
def host_resolves(host: str) -> bool:
    try:
        socket.getaddrinfo(host, 443)
        return True
    except OSError:
        return False


def require_host(host: str, label: str | None = None) -> None:
    if not host_resolves(host):
        name = label or host
        raise RuntimeError(f"{name} unavailable: cannot resolve {host}")
