from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class BoundingBox(BaseModel):
    top: int
    right: int
    bottom: int
    left: int


class FaceSnapshot(BaseModel):
    bounding_box: BoundingBox
    distance: Optional[float] = None
    person_id: Optional[str] = None


class PhotoIngestionResponse(BaseModel):
    id: str = Field(..., description="Newly stored photo id")
    original_filename: str
    labels: List[str] = Field(default_factory=list)
    media_url: str
    faces: List[FaceSnapshot]
    created_at: datetime


class MatchResult(BaseModel):
    photo_id: str
    media_url: str
    distance: Optional[float] = None
    labels: List[str] = Field(default_factory=list)
    matched_face: FaceSnapshot
    person_id: Optional[str] = None
    source_path: Optional[str] = Field(default=None, exclude=True)
    content_hash: Optional[str] = Field(default=None, exclude=True)
    original_source_path: Optional[str] = Field(default=None, exclude=True)


class SearchResponse(BaseModel):
    query_faces: int
    matches: List[MatchResult]
    report_url: Optional[str] = None
