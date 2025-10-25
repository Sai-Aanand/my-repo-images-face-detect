from __future__ import annotations

import uuid
from typing import List

from motor.motor_asyncio import AsyncIOMotorCollection

from app.core.config import get_settings
from app.core.database import get_photos_collection
from app.services.face_analyzer import face_analyzer


_settings = get_settings()


async def _faces_cursor(collection: AsyncIOMotorCollection):
    projection = {"faces": 1}
    cursor = collection.find({}, projection=projection)
    async for doc in cursor:
        for face in doc.get("faces", []):
            encoding = face.get("encoding")
            if encoding:
                yield face


async def assign_person_id(encoding: List[float]) -> str:
    """Return an existing person id if the embedding matches, else create a new one."""

    collection = get_photos_collection()
    cluster_threshold = face_analyzer.distance_threshold * _settings.person_id_distance_multiplier
    async for face in _faces_cursor(collection):
        distance = face_analyzer.face_distance(encoding, face["encoding"])
        if distance <= cluster_threshold:
            person_id = face.get("person_id")
            if person_id:
                return person_id
    return uuid.uuid4().hex


async def ensure_person_ids() -> None:
    """Assign person ids to any stored faces that predate clustering."""

    collection = get_photos_collection()
    cursor = collection.find({}, projection={"faces": 1})
    async for doc in cursor:
        updated_faces = []
        changed = False
        for face in doc.get("faces", []):
            if face.get("person_id"):
                updated_faces.append(face)
                continue
            face["person_id"] = uuid.uuid4().hex
            updated_faces.append(face)
            changed = True
        if changed:
            await collection.update_one({"_id": doc["_id"]}, {"$set": {"faces": updated_faces}})
