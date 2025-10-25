from __future__ import annotations

from typing import Dict

from motor.motor_asyncio import AsyncIOMotorCollection

from app.core.database import get_photos_collection


async def purge_duplicate_photos() -> Dict[str, int]:
    """Remove duplicate documents that share the same source hash."""

    collection: AsyncIOMotorCollection = get_photos_collection()
    pipeline = [
        {"$match": {"source_hash": {"$exists": True}}},
        {"$group": {"_id": "$source_hash", "ids": {"$push": "$_id"}, "count": {"$sum": 1}}},
        {"$match": {"count": {"$gt": 1}}},
    ]

    removed = 0
    async for group in collection.aggregate(pipeline):
        duplicate_ids = group["ids"][1:]
        if not duplicate_ids:
            continue
        result = await collection.delete_many({"_id": {"$in": duplicate_ids}})
        removed += result.deleted_count

    return {"removed": removed}
