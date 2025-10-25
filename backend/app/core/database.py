from typing import Optional

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection

from app.core.config import get_settings

_settings = get_settings()
_client: Optional[AsyncIOMotorClient] = None
_collection: Optional[AsyncIOMotorCollection] = None


async def connect_to_mongo() -> None:
    global _client, _collection
    if _client is not None:
        return
    _client = AsyncIOMotorClient(_settings.mongo_uri)
    db = _client[_settings.mongo_db_name]
    _collection = db[_settings.mongo_collection_name]


async def close_mongo_connection() -> None:
    global _client, _collection
    if _client is None:
        return
    _client.close()
    _client = None
    _collection = None


def get_photos_collection() -> AsyncIOMotorCollection:
    if _collection is None:
        raise RuntimeError("MongoDB collection is not initialised yet")
    return _collection
