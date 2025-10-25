from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, Optional

from motor.motor_asyncio import AsyncIOMotorCollection

from app.core.database import get_photos_collection
from app.services.storage_service import storage

logger = logging.getLogger(__name__)


async def ensure_media_file(
    collection: AsyncIOMotorCollection,
    document: dict,
    *,
    payload: bytes | None = None,
    filename: str | None = None,
) -> Optional[str]:
    """Make sure the media file referenced by a document exists on disk."""

    media_path = document.get("media_path")
    if media_path:
        absolute_path = storage.resolve_path(media_path)
        if absolute_path.exists():
            return media_path

    data = payload
    if data is None:
        source_path = document.get("source_path")
        if source_path:
            source_file = Path(source_path)
            if source_file.exists():
                try:
                    data = source_file.read_bytes()
                    filename = filename or source_file.name
                except OSError as exc:
                    logger.warning("Unable to read source file %s: %s", source_file, exc)

    if data is None:
        return None

    relative_path, _ = storage.save_bytes(data, filename or document.get("original_filename"))
    await collection.update_one({"_id": document["_id"]}, {"$set": {"media_path": relative_path}})
    return relative_path


async def rehydrate_media_files() -> Dict[str, int]:
    """Iterate over stored photos and re-create any missing media files."""

    collection = get_photos_collection()
    cursor = collection.find({}, projection={"media_path": 1, "source_path": 1, "original_filename": 1})
    restored = missing = 0
    async for doc in cursor:
        media_path = doc.get("media_path")
        if media_path and storage.resolve_path(media_path).exists():
            continue
        replacement = await ensure_media_file(collection, doc)
        if replacement:
            restored += 1
        else:
            missing += 1
            logger.warning("Media missing for photo %s and no source found", doc.get("_id"))

    return {"restored": restored, "still_missing": missing}
