from __future__ import annotations

import io
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from PIL import Image
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.utils import ImageReader, simpleSplit
from reportlab.pdfgen import canvas

from app.core.config import get_settings
from app.schemas.photo import MatchResult
from app.services.storage_service import storage

_settings = get_settings()


class SearchReporter:
    """Renders a PDF that contains the query image and the retrieved matches."""

    def __init__(self, media_root: Path):
        self._reports_root = media_root / "reports"
        self._reports_root.mkdir(parents=True, exist_ok=True)

    def build_report(
        self,
        *,
        query_filename: str | None,
        query_image: Optional[bytes],
        query_faces: int,
        matches: List[MatchResult],
    ) -> str:
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
        filename = f"search_{timestamp}.pdf"
        relative_path = Path("reports") / filename
        absolute_path = self._reports_root / filename
        self._render_pdf(
            output_path=absolute_path,
            query_filename=query_filename,
            query_image=query_image,
            query_faces=query_faces,
            matches=matches,
        )
        return relative_path.as_posix()

    def _render_pdf(
        self,
        *,
        output_path: Path,
        query_filename: str | None,
        query_image: Optional[bytes],
        query_faces: int,
        matches: List[MatchResult],
    ) -> None:
        buffer = io.BytesIO()
        pdf_canvas = canvas.Canvas(buffer, pagesize=LETTER)
        width, height = LETTER
        margin = 48
        line_height = 14

        def _reset_page(font_name: str = "Helvetica", font_size: int = line_height) -> float:
            pdf_canvas.showPage()
            pdf_canvas.setFont(font_name, font_size)
            return height - margin

        def draw_lines(lines: List[str], bold: bool = False, spacing: int = 4) -> float:
            nonlocal current_y
            font_name = "Helvetica-Bold" if bold else "Helvetica"
            pdf_canvas.setFont(font_name, line_height)
            for text in lines:
                wrapped = simpleSplit(text, font_name, line_height, width - 2 * margin)
                for fragment in wrapped:
                    if current_y <= margin:
                        current_y = _reset_page(font_name)
                    pdf_canvas.drawString(margin, current_y, fragment)
                    current_y -= line_height + spacing
            return current_y

        def _optimized_reader(data: bytes) -> ImageReader:
            with Image.open(io.BytesIO(data)) as image:
                image = image.convert("RGB")
                image.thumbnail((800, 800), Image.LANCZOS)
                optimized = io.BytesIO()
                image.save(optimized, format="JPEG", quality=70, optimize=True)
                optimized.seek(0)
            return ImageReader(optimized)

        def draw_image(image_bytes: bytes, max_width: float, max_height: float, x: float, y: float) -> float:
            reader = _optimized_reader(image_bytes)
            img_width, img_height = reader.getSize()
            scale = min(max_width / img_width, max_height / img_height, 1.0)
            draw_width = img_width * scale
            draw_height = img_height * scale
            pdf_canvas.drawImage(reader, x, y - draw_height, width=draw_width, height=draw_height, preserveAspectRatio=True)
            return draw_height

        current_y = height - margin
        pdf_canvas.setFont("Helvetica-Bold", 18)
        pdf_canvas.drawString(margin, current_y, "Face Search Report")
        current_y -= 28

        pdf_canvas.setFont("Helvetica", line_height)
        meta_lines = [
            f"Generated at: {datetime.utcnow().isoformat()} UTC",
            f"Query filename: {query_filename or 'unnamed upload'}",
            f"Faces detected in query: {query_faces}",
            f"Matches returned: {len(matches)}",
        ]
        draw_lines(meta_lines, spacing=6)

        if query_image:
            if current_y - 220 <= margin:
                current_y = _reset_page()
            pdf_canvas.setFont("Helvetica-Bold", line_height)
            pdf_canvas.drawString(margin, current_y, "Query image")
            current_y -= line_height + 8
            drawn_height = draw_image(query_image, max_width=width - 2 * margin, max_height=200, x=margin, y=current_y)
            current_y -= drawn_height + 16

        if matches:
            if current_y <= margin:
                current_y = _reset_page()
            pdf_canvas.setFont("Helvetica-Bold", line_height)
            pdf_canvas.drawString(margin, current_y, "Matches")
            current_y -= line_height + 12

        thumb_max_width = width - 2 * margin
        thumb_max_height = 220

        for idx, match in enumerate(matches, start=1):
            required_space = thumb_max_height + (line_height * 4) + 24
            if current_y - required_space <= margin:
                current_y = _reset_page()
                pdf_canvas.setFont("Helvetica-Bold", line_height)
                pdf_canvas.drawString(margin, current_y, "Matches (cont.)")
                current_y -= line_height + 12

            image_bytes = None
            for candidate in (match.source_path, match.original_source_path):
                if not candidate:
                    continue
                image_bytes = storage.read_bytes(candidate)
                if image_bytes:
                    break

            distance = "n/a" if match.distance is None else f"{match.distance:.3f}"
            person_text = match.person_id or match.matched_face.person_id or "unknown"
            labels_text = ", ".join(match.labels) if match.labels else "none"

            pdf_canvas.setFont("Helvetica-Bold", line_height)
            pdf_canvas.drawString(margin, current_y, f"{idx}. Match")
            current_y -= line_height + 4

            pdf_canvas.setFont("Helvetica", line_height)
            pdf_canvas.drawString(margin, current_y, f"Distance: {distance}")
            current_y -= line_height + 2
            pdf_canvas.drawString(margin, current_y, f"Person ID: {person_text}")
            current_y -= line_height + 2
            pdf_canvas.drawString(margin, current_y, f"Labels: {labels_text}")
            current_y -= line_height + 6

            if image_bytes:
                drawn_height = draw_image(image_bytes, thumb_max_width, thumb_max_height, margin, current_y)
                current_y -= drawn_height + 16
            else:
                pdf_canvas.drawString(margin, current_y, "Image unavailable")
                current_y -= line_height + 16

        pdf_canvas.save()
        buffer.seek(0)
        output_path.write_bytes(buffer.read())


search_reporter = SearchReporter(_settings.media_root)
