from __future__ import annotations

import io
from dataclasses import dataclass
from typing import List

import face_recognition
import numpy as np

from app.core.config import get_settings

_settings = get_settings()


@dataclass
class FaceEmbedding:
    encoding: List[float]
    bounding_box: dict


class FaceAnalyzer:
    def __init__(self, distance_threshold: float = 0.45):
        self.distance_threshold = distance_threshold

    def extract_embeddings(self, image_bytes: bytes) -> List[FaceEmbedding]:
        buffer = io.BytesIO(image_bytes)
        buffer.seek(0)
        image = face_recognition.load_image_file(buffer)
        locations = face_recognition.face_locations(image)
        encodings = face_recognition.face_encodings(image, known_face_locations=locations)
        embeddings: List[FaceEmbedding] = []
        for location, encoding in zip(locations, encodings):
            top, right, bottom, left = location
            embeddings.append(
                FaceEmbedding(
                    encoding=encoding.tolist(),
                    bounding_box={
                        "top": int(top),
                        "right": int(right),
                        "bottom": int(bottom),
                        "left": int(left),
                    },
                )
            )
        return embeddings

    @staticmethod
    def face_distance(encoding_a: List[float], encoding_b: List[float]) -> float:
        vector_a = np.array(encoding_a)
        vector_b = np.array(encoding_b)
        return float(np.linalg.norm(vector_a - vector_b))


face_analyzer = FaceAnalyzer(distance_threshold=_settings.face_distance_threshold)
