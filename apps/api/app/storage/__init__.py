"""StorageProvider interface (RULES.md: all file I/O via this).
class StorageProvider(Protocol):
    async def save(data: bytes, key_hint: str, purpose: str) -> str   # returns storage_key
    async def open(storage_key: str) -> bytes
    async def delete(storage_key: str) -> None
Selected by config/storage.yaml. local.py = Phase 1; s3.py = future drop-in via config."""
