"""Render endpoint.

Takes a Note and a render spec, returns a PDF. No database yet -- the note
comes in the request body and the PDF goes straight back in the response.
"""

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from app.notes.schema import Note
from app.render.handwriting import style_ids
from app.render.paper import paper_ids
from app.render.service import RenderSpec, render_to_bytes
from app.render.template import template_ids

router = APIRouter(tags=["render"])


class RenderRequest(BaseModel):
    note: Note
    template_id: str = "lecture"
    style_id: str = "patrick_hand"
    paper_id: str = "plain"
    seed: int = Field(default=0, ge=0)
    scale: float = Field(default=1.0, ge=0.6, le=1.8)


@router.post(
    "/render",
    response_class=Response,
    responses={200: {"content": {"application/pdf": {}}}},
)
async def render(request: RenderRequest) -> Response:
    for value, allowed, label in (
        (request.template_id, template_ids(), "template_id"),
        (request.style_id, style_ids(), "style_id"),
        (request.paper_id, paper_ids(), "paper_id"),
    ):
        if value not in allowed:
            raise HTTPException(422, f"unknown {label} '{value}'. Allowed: {allowed}")

    spec = RenderSpec(
        template_id=request.template_id,
        style_id=request.style_id,
        paper_id=request.paper_id,
        seed=request.seed,
        scale=request.scale,
    )

    # Rendering is synchronous CPU work. Awaiting it directly would block the
    # event loop and stall every other request on this worker.
    result = await run_in_threadpool(render_to_bytes, request.note, spec)

    return Response(
        content=result.pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": 'inline; filename="note.pdf"',
            "X-Page-Count": str(result.page_count),
        },
    )
