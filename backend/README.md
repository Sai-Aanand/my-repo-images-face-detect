# Backend: Face Image Detection API

FastAPI service that indexes face encodings for uploaded photos and searches for matches across the collection using `face_recognition` + MongoDB.

## Prerequisites

- Python 3.10+
- MongoDB running locally (`mongodb://localhost:27017` by default)
- System packages needed by [`face-recognition`](https://github.com/ageitgey/face_recognition) (CMake, dlib build deps, ideally install via `brew install cmake pkg-config` on macOS)

## Setup

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env  # adjust values if necessary
```

## Running

```bash
uvicorn app.main:app --reload --app-dir backend
```

The API serves media files under `/media` (e.g. `http://localhost:8000/media/uploads/<file>.jpg`).

## Key Endpoints

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/api/v1/health` | Readiness probe |
| `POST` | `/api/v1/photos` | Upload/index a photo; accepts multipart file + optional `labels` field (comma-separated) |
| `POST` | `/api/v1/search` | Upload a query face photo. Returns matching photo ids/media URLs ordered by similarity |

### Example Requests

Upload/index:

```bash
curl -X POST http://localhost:8000/api/v1/photos \
  -F "file=@/path/to/photo.jpg" \
  -F "labels=family,vacation"
```

Search:

```bash
curl -X POST http://localhost:8000/api/v1/search \
  -F "file=@/path/to/person.jpg"
```

Response excerpt:

```json
{
  "query_faces": 1,
  "matches": [
    {
      "photo_id": "662f...",
      "media_url": "/media/uploads/uuid.jpg",
      "distance": 0.37,
      "labels": ["family"],
      "matched_face": {
        "bounding_box": {"top": 120, "right": 310, "bottom": 420, "left": 40},
        "distance": 0.37
      }
    }
  ],
  "report_url": "/media/reports/search_20240501_123000.pdf"
}
```

## Notes & Next Steps

- Only the first detected face from the search photo is compared today; extend `search_by_face` to iterate over every query face if you need multi-face queries.
- Consider caching embeddings or using a vector database for large datasets.
- Add authentication/authorization plus better error handling before production use.
