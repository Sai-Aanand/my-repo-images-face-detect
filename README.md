# Face Image Detection

End-to-end local project that indexes a library of people + group photos and finds every appearance of a selected person. Upload a solo image via the UI, the FastAPI backend extracts a face embedding, compares it with stored embeddings in MongoDB, and returns every photo that contains the same individual.

## Architecture

- **Frontend (React + Vite + TypeScript)** – Minimal “search-only” interface that uploads a single portrait and renders the matches.
- **Backend (FastAPI)** – Watches a dataset folder, handles face detection (`face_recognition`), clusters recurring faces, and powers similarity search.
- **MongoDB** – Stores metadata for each indexed photo plus one or more face encodings per image.
- **Local media storage** – Uploaded files persist under `backend/media` and are exposed at `/media` for the frontend to read.

1. Point the backend to your existing photo library via `DATASET_PATH` in `backend/.env`.
2. On startup, FastAPI scans the folder, stores the media in `backend/media/uploads`, assigns a `person_id` to every detected face (so all of that person’s photos are linked together), and writes encodings to MongoDB.
3. The React UI uploads a single portrait, hits `/api/v1/search`, and displays the closest matches plus the entire cluster (`person_id`) where that individual appears.

## Prerequisites

- Python 3.10+
- Node.js 18+
- MongoDB running locally (or connection string in `backend/.env`)
- System deps for [`face_recognition`](https://github.com/ageitgey/face_recognition#installation) (CMake, dlib build chain). On macOS: `brew install cmake pkg-config`.

## Backend Setup

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt  # installs FastAPI + face_recognition + models
cp .env.example .env
```

By default the backend scans `/Users/aanand/Downloads/Collection`. If you want to change the folder, edit `.env` and set:

```
DATASET_PATH="/your/custom/path"
DATASET_LABELS=collection-name,optional-tags
# Optional: disable automatic dataset scans on every server boot
# AUTO_INGEST_ON_STARTUP=false
```
(quote paths that contain spaces or non-Latin characters).

Finally run:

```bash
uvicorn app.main:app --reload --app-dir backend
```

The first startup scans the entire dataset path; depending on the folder size it may take a few minutes before the API is ready to serve traffic.

Key endpoints:

- `POST /api/v1/photos` – multipart upload for dataset indexing (`file`, optional `labels`)
- `POST /api/v1/search` – upload a single-person photo, returns ordered matches with confidence + labels (default similarity threshold `FACE_DISTANCE_THRESHOLD=0.6`, tweak in `.env`)
- The backend drops duplicate photos automatically by hashing media files, so every restart reuses the same records instead of re-indexing the dataset.
- `GET /media/{path}` – serves raw media for use in the UI

## Frontend Setup

```bash
cd frontend
cp .env.example .env            # ensures the API base URL points to FastAPI (default http://localhost:8000)
npm install
npm run dev                     # Vite dev server on http://localhost:5173
```

The UI focuses solely on searching: drop/upload a single face in the hero card and the grid renders every matching photo.

## Typical Flow

1. Start MongoDB locally and boot the FastAPI server (it will ingest `DATASET_PATH` automatically).
2. Open the React app, upload a front-facing portrait, and wait for the matches.
3. Review matches + labels, optionally re-run with another image.

### Optional: Manual bulk ingestion

The backend automatically ingests `DATASET_PATH` on startup, but you can still run the standalone helper if you want to process an arbitrary folder on demand:

```bash
python backend/scripts/bulk_index.py /some/other/folder --labels "event,2022"
```

## Extending the Project

- Move embeddings into a vector database (e.g., Qdrant, Weaviate) once the dataset grows.
- Add authentication + rate limiting before exposing beyond local use.
- Track richer metadata (event, location) to filter the match results grid.
- Add a filesystem watcher to ingest new files as soon as they land in the dataset folder.
- For even stricter matching, adjust the optional `SEARCH_DISTANCE_MULTIPLIER` (default 0.92) or `PERSON_ID_DISTANCE_MULTIPLIER` (default 0.9) in `backend/.env` to fine-tune how aggressively results are filtered.
- Set `AUTO_INGEST_ON_STARTUP=false` when you prefer to ingest on demand (e.g., run `python backend/scripts/bulk_index.py …`) to avoid repeated console logs for large collections while developing with `uvicorn --reload`.
