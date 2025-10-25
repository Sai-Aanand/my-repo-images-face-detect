import hashlib
import uuid
from pathlib import Path
from typing import Optional, Tuple

from app.core.config import get_settings

_settings = get_settings()


class MediaStorage:
    """Handles storing binary payloads on disk."""

    def __init__(self, media_root: Path):
        self.media_root = media_root
        self.media_root.mkdir(parents=True, exist_ok=True)

    def save_bytes(self, data: bytes, original_filename: str | None = None) -> Tuple[str, Path]:
        suffix = Path(original_filename or "uploaded").suffix.lower() or ".jpg"
        relative_path = Path("uploads") / f"{uuid.uuid4().hex}{suffix}"
        absolute_path = self.media_root / relative_path
        absolute_path.parent.mkdir(parents=True, exist_ok=True)
        absolute_path.write_bytes(data)
        return relative_path.as_posix(), absolute_path

    def build_media_url(self, relative_path: str) -> str:
        base = _settings.media_url_prefix.rstrip("/")
        rel = relative_path.lstrip("/")
        return f"{base}/{rel}"

    def resolve_path(self, relative_path: str | Path) -> Path:
        path = Path(relative_path)
        if path.is_absolute():
            return path
        return self.media_root / path

    def read_bytes(self, relative_path: str | Path) -> Optional[bytes]:
        absolute_path = self.resolve_path(relative_path)
        if not absolute_path.exists():
            return None
        return absolute_path.read_bytes()

    def compute_hash(self, relative_path: str | Path) -> Optional[str]:
        absolute_path = self.resolve_path(relative_path)
        if not absolute_path.exists():
            return None
        hasher = hashlib.md5()
        with absolute_path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(8192), b""):
                if not chunk:
                    break
                hasher.update(chunk)
        return hasher.hexdigest()


storage = MediaStorage(_settings.media_root)
