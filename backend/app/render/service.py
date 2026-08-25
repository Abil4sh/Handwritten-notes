"""Render service.

Wraps the page renderer in the shape the API needs: takes a Note plus a render
spec, returns PDF bytes. Nothing here knows about HTTP.
"""

import tempfile
from dataclasses import dataclass
from pathlib import Path

from app.notes.schema import Note
from app.render.page_renderer import render_note


@dataclass(frozen=True)
class RenderSpec:
    template_id: str = "lecture"
    style_id: str = "patrick_hand"
    paper_id: str = "plain"
    seed: int = 0
    scale: float = 1.0


@dataclass(frozen=True)
class RenderResult:
    pdf: bytes
    page_count: int


def render_to_bytes(note: Note, spec: RenderSpec) -> RenderResult:
    """Render a note to PDF in memory.

    ReportLab writes to a path, so we use a temporary file and read it back.
    The file is deleted as soon as this function returns; nothing persists on
    the server's disk, which matters because that disk is ephemeral in
    production and would not survive a redeploy.
    """
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "note.pdf"
        pages = render_note(
            note,
            str(path),
            style_id=spec.style_id,
            paper_id=spec.paper_id,
            template_id=spec.template_id,
            seed=spec.seed,
            scale=spec.scale,
        )
        return RenderResult(pdf=path.read_bytes(), page_count=pages)
