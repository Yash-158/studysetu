"""StorageProvider interface (RULES.md: all file I/O via this).
class StorageProvider(Protocol):
    async def save(data: bytes, key_hint: str, purpose: str) -> str   # returns storage_key
    async def open(storage_key: str) -> bytes
    async def delete(storage_key: str) -> None
Selected by config/storage.yaml. local.py = Phase 1; s3.py = future drop-in via config."""
from __future__ import annotations

from typing import Protocol


class StorageProvider(Protocol):
    async def save(self, data: bytes, key_hint: str, purpose: str) -> str: ...
    async def open(self, storage_key: str) -> bytes: ...
    async def delete(self, storage_key: str) -> None: ...
