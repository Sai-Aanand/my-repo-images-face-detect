from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Iterable, List

from app.core.database import get_photos_collection
from app.services.face_analyzer import FaceEmbedding, face_analyzer
from app.services.media_rehydrator import ensure_media_file
from app.services.person_identifier import assign_person_id
from app.services.storage_service import storage

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp"}
logger = logging.getLogger(__name__)


def iter_image_files(root: Path) -> Iterable[Path]:
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS:
            yield path


def _hash_bytes(data: bytes) -> str:
    import hashlib

    return hashlib.sha256(data).hexdigest()


async def ingest_dataset(dataset_root: Path, default_labels: List[str] | None = None) -> dict:
    """Walk a folder, ingesting every supported image into MongoDB."""

    if default_labels is None:
        default_labels = []

    dataset_root = dataset_root.expanduser().resolve()
    if not dataset_root.exists():
        logger.warning("Dataset root %s does not exist", dataset_root)
        return {"processed": 0, "indexed": 0, "skipped": 0, "reason": "missing dataset"}

    collection = get_photos_collection()
    processed = indexed = skipped = 0

    for file_path in iter_image_files(dataset_root):
        processed += 1
        try:
            payload = file_path.read_bytes()
        except OSError as exc:  # file might disappear mid-run
            skipped += 1
            logger.warning("Cannot read %s: %s", file_path, exc)
            continue

        if not payload:
            skipped += 1
            logger.debug("Empty file skipped: %s", file_path)
            continue

        embeddings: List[FaceEmbedding] = face_analyzer.extract_embeddings(payload)
        if not embeddings:
            skipped += 1
            logger.debug("No faces detected in %s", file_path)
            continue

        doc_hash = _hash_bytes(payload)
        existing = await collection.find_one({"source_hash": doc_hash})
        if existing:
            await ensure_media_file(collection, existing, payload=payload, filename=file_path.name)
            skipped += 1
            continue

        relative_path, _ = storage.save_bytes(payload, original_filename=file_path.name)
        faces_payload = []
        for embedding in embeddings:
            person_id = await assign_person_id(embedding.encoding)
            faces_payload.append(
                {
                    "encoding": embedding.encoding,
                    "bounding_box": embedding.bounding_box,
                    "person_id": person_id,
                }
            )

        await collection.insert_one(
            {
                "original_filename": file_path.name,
                "labels": default_labels,
                "media_path": relative_path,
                "faces": faces_payload,
                "created_at": datetime.utcnow(),
                "source_path": str(file_path),
                "source_hash": doc_hash,
            }
        )
        indexed += 1
        logger.info("Indexed %s (%d face(s))", file_path, len(embeddings))

    return {"processed": processed, "indexed": indexed, "skipped": skipped}
