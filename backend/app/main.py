import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.routes import router as api_router
from app.core.config import get_settings
from app.core.database import close_mongo_connection, connect_to_mongo
from app.services.dataset_ingestor import ingest_dataset
from app.services.person_identifier import ensure_person_ids
from app.services.photo_deduplicator import purge_duplicate_photos
from app.services.media_rehydrator import rehydrate_media_files

settings = get_settings()
logger = logging.getLogger(__name__)

app = FastAPI(title=settings.app_name, version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allow_origins or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event() -> None:
    await connect_to_mongo()
    settings.media_root.mkdir(parents=True, exist_ok=True)
    await ensure_person_ids()
    if settings.auto_ingest_on_startup and settings.dataset_path:
        result = await ingest_dataset(settings.dataset_path, settings.dataset_labels)
        logger.info(
            "Dataset ingestion complete",
            extra={"processed": result.get("processed"), "indexed": result.get("indexed")},
        )
    cleanup = await purge_duplicate_photos()
    if cleanup.get("removed"):
        logger.info("Removed duplicate photos", extra=cleanup)
    rehydration = await rehydrate_media_files()
    if any(rehydration.values()):
        logger.info("Media rehydration results", extra=rehydration)


@app.on_event("shutdown")
async def shutdown_event() -> None:
    await close_mongo_connection()


app.include_router(api_router)
app.mount(settings.media_url_prefix, StaticFiles(directory=settings.media_root), name="media")
