"""LocalStorageProvider -> writes under storage.upload_dir (uploads_data volume in prod).
Retention cleanup (WHERE expires_at < now() AND deleted_at IS NULL -> delete file, soft-delete row)
is TTL-only (Phase 2 doubt photos); materials/submissions are permanent per storage.yaml and need
no cleanup job (M3 scope: implements save/open/delete only)."""
from __future__ import annotations

import asyncio
import uuid
from pathlib import Path

from app.core.config import settings


class LocalStorageProvider:
    def __init__(self, base_dir: str | None = None) -> None:
        self._base_dir = Path(base_dir or settings.get("storage", "upload_dir", default="/data/uploads"))

    def _path(self, storage_key: str) -> Path:
        return self._base_dir / storage_key

    async def save(self, data: bytes, key_hint: str, purpose: str) -> str:
        safe_hint = "".join(c for c in key_hint if c.isalnum() or c in "._-") or "file"
        storage_key = f"{purpose}/{uuid.uuid4()}-{safe_hint}"

        def _write() -> None:
            path = self._path(storage_key)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)

        await asyncio.to_thread(_write)
        return storage_key

    async def open(self, storage_key: str) -> bytes:
        return await asyncio.to_thread(self._path(storage_key).read_bytes)

    async def delete(self, storage_key: str) -> None:
        def _delete() -> None:
            self._path(storage_key).unlink(missing_ok=True)

        await asyncio.to_thread(_delete)
