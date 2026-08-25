"""Render records: produce a PDF for a saved note and keep it."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from app.auth.dependencies import get_current_user
from app.db import notes_repo, renders_repo
from app.db.hashing import spec_hash as compute_spec_hash
from app.notes.schema import Note
from app.render.handwriting import style_ids
from app.render.paper import paper_ids
from app.render.service import RenderSpec, render_to_bytes
from app.render.template import template_ids

router = APIRouter(tags=["renders"])


class CreateRenderRequest(BaseModel):
    template_id: str = "lecture"
    style_id: str = "patrick_hand"
    paper_id: str = "plain"


def validate(request: CreateRenderRequest) -> dict:
    spec = request.model_dump()
    for value, allowed, label in (
        (request.template_id, template_ids(), "template_id"),
        (request.style_id, style_ids(), "style_id"),
        (request.paper_id, paper_ids(), "paper_id"),
    ):
        if value not in allowed:
            raise HTTPException(422, f"unknown {label} '{value}'. Allowed: {allowed}")
    return spec


def present(row: dict) -> dict:
    return {
        "id": row["id"],
        "status": row["status"],
        "page_count": row.get("page_count"),
        "download_url": renders_repo.signed_url(row["storage_path"])
        if row.get("storage_path")
        else None,
    }


@router.post("/notes/{note_id}/renders", status_code=201)
async def create(
    note_id: UUID,
    request: CreateRenderRequest,
    user_id: UUID = Depends(get_current_user),
) -> dict:
    spec = validate(request)

    note_row = await run_in_threadpool(notes_repo.get_note, user_id, note_id)
    if not note_row:
        raise HTTPException(404, "Note not found")

    key = compute_spec_hash(note_row["content_hash"], spec)

    cached = await run_in_threadpool(renders_repo.find_cached, user_id, note_id, key)
    if cached:
        return await run_in_threadpool(present, cached)

    note = Note.model_validate(note_row["content"])
    result = await run_in_threadpool(render_to_bytes, note, RenderSpec(**spec))
    row = await run_in_threadpool(
        renders_repo.store_render, user_id, note_id, spec, key, result.pdf, result.page_count
    )
    return await run_in_threadpool(present, row)


@router.get("/renders/{render_id}")
async def show(render_id: UUID, user_id: UUID = Depends(get_current_user)) -> dict:
    row = await run_in_threadpool(renders_repo.get_render, user_id, render_id)
    if not row:
        raise HTTPException(404, "Render not found")
    return await run_in_threadpool(present, row)
