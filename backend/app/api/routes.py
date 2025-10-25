import hashlib
import logging
from datetime import datetime
from math import inf
from typing import List

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from motor.motor_asyncio import AsyncIOMotorCollection

from app.core.config import get_settings
from app.core.database import get_photos_collection
from app.schemas.photo import BoundingBox, FaceSnapshot, MatchResult, PhotoIngestionResponse, SearchResponse
from app.services.face_analyzer import FaceEmbedding, face_analyzer
from app.services.person_identifier import assign_person_id
from app.services.media_rehydrator import ensure_media_file
from app.services.search_reporter import search_reporter
from app.services.storage_service import storage

router = APIRouter(prefix="/api/v1")
_settings = get_settings()
logger = logging.getLogger(__name__)


def _parse_labels(raw: str | None) -> List[str]:
    if not raw:
        return []
    return [label.strip() for label in raw.split(",") if label.strip()]


@router.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@router.post("/photos", response_model=PhotoIngestionResponse, status_code=201)
async def index_photo(
    file: UploadFile = File(...),
    labels: str | None = Form(default=None),
    collection: AsyncIOMotorCollection = Depends(get_photos_collection),
) -> PhotoIngestionResponse:
    payload = await file.read()
    if not payload:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    photo_hash = hashlib.sha256(payload).hexdigest()

    embeddings: List[FaceEmbedding] = face_analyzer.extract_embeddings(payload)
    if not embeddings:
        raise HTTPException(status_code=400, detail="No faces detected in the uploaded image")

    existing_doc = await collection.find_one({"source_hash": photo_hash})
    if existing_doc:
        return PhotoIngestionResponse(
            id=str(existing_doc["_id"]),
            original_filename=existing_doc.get("original_filename", file.filename),
            labels=existing_doc.get("labels", []),
            media_url=storage.build_media_url(existing_doc["media_path"]),
            faces=[
                FaceSnapshot(
                    bounding_box=BoundingBox(**face["bounding_box"]),
                    person_id=face.get("person_id"),
                )
                for face in existing_doc.get("faces", [])
            ],
            created_at=existing_doc.get("created_at", datetime.utcnow()),
        )

    relative_path, _absolute_path = storage.save_bytes(payload, file.filename)
    labels_list = _parse_labels(labels)
    created_at = datetime.utcnow()

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

    document = {
        "original_filename": file.filename,
        "labels": labels_list,
        "media_path": relative_path,
        "faces": faces_payload,
        "created_at": created_at,
        "source_hash": photo_hash,
    }

    insert_result = await collection.insert_one(document)

    response = PhotoIngestionResponse(
        id=str(insert_result.inserted_id),
        original_filename=file.filename,
        labels=labels_list,
        media_url=storage.build_media_url(relative_path),
        faces=
        [
            FaceSnapshot(
                bounding_box=BoundingBox(**embedding.bounding_box),
                person_id=faces_payload[idx]["person_id"],
            )
            for idx, embedding in enumerate(embeddings)
        ],
        created_at=created_at,
    )
    return response


async def _ensure_media(doc: dict, collection: AsyncIOMotorCollection) -> str | None:
    media_path = doc.get("media_path")
    if media_path and storage.resolve_path(media_path).exists():
        return media_path
    return await ensure_media_file(collection, doc)


@router.post("/search", response_model=SearchResponse)
async def search_by_face(
    file: UploadFile = File(...),
    limit: int = Query(default=_settings.max_results, ge=1, le=_settings.max_results),
    collection: AsyncIOMotorCollection = Depends(get_photos_collection),
) -> SearchResponse:
    payload = await file.read()
    if not payload:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    query_embeddings: List[FaceEmbedding] = face_analyzer.extract_embeddings(payload)
    if not query_embeddings:
        raise HTTPException(status_code=400, detail="No faces detected in the query image")

    entries: list[tuple[MatchResult, int]] = []
    effective_threshold = face_analyzer.distance_threshold * _settings.search_distance_multiplier
    hash_cache: dict[str, str | None] = {}

    def _media_hash(relative_path: str | None) -> str | None:
        if not relative_path:
            return None
        if relative_path not in hash_cache:
            hash_cache[relative_path] = storage.compute_hash(relative_path)
        return hash_cache[relative_path]

    projection = {"original_filename": 1, "labels": 1, "media_path": 1, "faces": 1, "source_path": 1}
    cursor = collection.find({}, projection=projection)
    async for doc in cursor:
        faces = doc.get("faces", [])
        if not faces:
            continue
        best_match: MatchResult | None = None
        best_votes = 0
        best_distance = inf
        for stored_face in faces:
            encoding = stored_face.get("encoding")
            if not encoding:
                continue
            face_votes = 0
            face_best_distance = inf
            face_candidate: MatchResult | None = None
            for query_embedding in query_embeddings:
                distance = face_analyzer.face_distance(query_embedding.encoding, encoding)
                if distance <= effective_threshold:
                    face_votes += 1
                    if distance < face_best_distance:
                        face_best_distance = distance
                    snapshot = FaceSnapshot(
                        bounding_box=BoundingBox(**stored_face["bounding_box"]),
                        distance=distance,
                        person_id=stored_face.get("person_id"),
                    )
                    media_path = await _ensure_media(doc, collection)
                    if not media_path:
                        continue
                    source_path = doc.get("source_path")
                    source_fallback = source_path if source_path and source_path != media_path else None
                    face_candidate = MatchResult(
                        photo_id=str(doc["_id"]),
                        media_url=storage.build_media_url(media_path),
                        distance=distance,
                        labels=doc.get("labels", []),
                        matched_face=snapshot,
                        person_id=stored_face.get("person_id"),
                        source_path=media_path,
                        content_hash=_media_hash(media_path),
                        original_source_path=source_fallback,
                    )
            if face_candidate and (
                best_match is None
                or face_votes > best_votes
                or (face_votes == best_votes and face_best_distance < best_distance)
            ):
                best_match = face_candidate
                best_votes = face_votes
                best_distance = face_best_distance
        if best_match:
            entries.append((best_match, best_votes))

    def _is_better(new_entry: tuple[MatchResult, int], existing_entry: tuple[MatchResult, int]) -> bool:
        new_result, new_votes = new_entry
        existing_result, existing_votes = existing_entry
        if new_votes != existing_votes:
            return new_votes > existing_votes
        new_distance = new_result.distance if new_result.distance is not None else inf
        existing_distance = existing_result.distance if existing_result.distance is not None else inf
        return new_distance < existing_distance

    unique_by_media: dict[str, tuple[MatchResult, int]] = {}
    for entry in entries:
        media_key = entry[0].content_hash or entry[0].media_url
        existing = unique_by_media.get(media_key)
        if existing is None or _is_better(entry, existing):
            unique_by_media[media_key] = entry

    ranked_entries = sorted(
        unique_by_media.values(),
        key=lambda entry: (
            -entry[1],
            entry[0].distance if entry[0].distance is not None else inf,
        ),
    )
    ranked_entries = ranked_entries[:limit]
    matches: List[MatchResult] = [entry[0] for entry in ranked_entries]
    match_map: dict[str, MatchResult] = {match.photo_id: match for match in matches}
    media_seen = {match.content_hash or match.media_url for match in matches}

    # Expand to include the entire cluster for the top person id.
    if matches and len(matches) < limit:
        primary_match = matches[0]
        primary_person_id = primary_match.person_id or primary_match.matched_face.person_id
        cluster_gate = effective_threshold
        if (
            primary_person_id
            and primary_match.distance is not None
            and primary_match.distance <= cluster_gate
        ):
            cluster_cursor = collection.find(
                {"faces.person_id": primary_person_id}, projection=projection
            )
            async for doc in cluster_cursor:
                if len(matches) >= limit:
                    break
                photo_id = str(doc["_id"])
                if photo_id in match_map:
                    continue
                face = next(
                    (face for face in doc.get("faces", []) if face.get("person_id") == primary_person_id),
                    None,
                )
                if not face:
                    continue
                face_encoding = face.get("encoding")
                if not face_encoding:
                    continue
                best_cluster_distance = min(
                    face_analyzer.face_distance(query_embedding.encoding, face_encoding)
                    for query_embedding in query_embeddings
                )
                if best_cluster_distance > effective_threshold:
                    continue
                snapshot = FaceSnapshot(
                    bounding_box=BoundingBox(**face["bounding_box"]),
                    distance=None,
                    person_id=primary_person_id,
                )
                media_path = await _ensure_media(doc, collection)
                if not media_path:
                    continue
                source_path = doc.get("source_path")
                source_fallback = source_path if source_path and source_path != media_path else None
                extra_match = MatchResult(
                    photo_id=photo_id,
                    media_url=storage.build_media_url(media_path),
                    distance=None,
                    labels=doc.get("labels", []),
                    matched_face=snapshot,
                    person_id=primary_person_id,
                    source_path=media_path,
                    content_hash=_media_hash(media_path),
                    original_source_path=source_fallback,
                )
                content_key = extra_match.content_hash or extra_match.media_url
                if photo_id in match_map or content_key in media_seen:
                    continue
                match_map[photo_id] = extra_match
                media_seen.add(content_key)
                matches.append(extra_match)

    filtered_matches: List[MatchResult] = []
    for match in matches:
        if match.distance is None or match.distance <= effective_threshold:
            filtered_matches.append(match)
    if not filtered_matches and ranked_entries:
        filtered_matches = [ranked_entries[0][0]]

    if len(filtered_matches) < limit:
        used_ids = {match.photo_id for match in filtered_matches}
        for entry in ranked_entries:
            candidate = entry[0]
            if candidate.photo_id in used_ids:
                continue
            filtered_matches.append(candidate)
            used_ids.add(candidate.photo_id)
            if len(filtered_matches) >= limit:
                break

    matches = filtered_matches[:limit]

    report_url = None
    try:
        report_path = search_reporter.build_report(
            query_filename=file.filename,
            query_image=payload,
            query_faces=len(query_embeddings),
            matches=matches,
        )
        report_url = storage.build_media_url(report_path)
    except Exception as exc:  # pragma: no cover - best-effort and not critical for search results
        logger.warning("Failed to build search report: %s", exc)

    return SearchResponse(query_faces=len(query_embeddings), matches=matches, report_url=report_url)
