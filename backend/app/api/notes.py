"""Notes API.

/notes/structure stays public so the no-login demo page keeps working.
Everything that touches the database requires a token.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from app.auth.dependencies import get_current_user
from app.db import notes_repo
from app.notes.schema import Note
from app.notes.structure import structure_note
from app.notes.transcript import clean_transcript

router = APIRouter(tags=["notes"])

MAX_INPUT_CHARS = 8000


class StructureRequest(BaseModel):
    raw_text: str = Field(min_length=1, max_length=MAX_INPUT_CHARS)


class TranscriptRequest(BaseModel):
    transcript: str = Field(min_length=1, max_length=40000)
    title: str | None = None


class CreateNoteRequest(BaseModel):
    raw_text: str = Field(min_length=1, max_length=MAX_INPUT_CHARS)


class UpdateNoteRequest(BaseModel):
    note: Note


@router.post("/notes/structure")
async def structure(request: StructureRequest) -> Note:
    """Public: raw text to structured note, nothing saved."""
    return await run_in_threadpool(structure_note, request.raw_text)


@router.post("/notes/from-transcript")
async def from_transcript(request: TranscriptRequest) -> dict:
    """Public: speech transcript -> marked-up text the editor can show.

    Returns the text rather than a Note so the person can read and correct it
    before it becomes a page. Speech recognition makes mistakes; hiding the
    intermediate step would hide them too.
    """
    text = await run_in_threadpool(clean_transcript, request.transcript, request.title)
    return {"raw_text": text}


@router.post("/notes", status_code=201)
async def create(
    request: CreateNoteRequest, user_id: UUID = Depends(get_current_user)
) -> dict:
    note = await run_in_threadpool(structure_note, request.raw_text)
    return await run_in_threadpool(
        notes_repo.create_note, user_id, note, request.raw_text
    )


@router.get("/notes")
async def index(user_id: UUID = Depends(get_current_user)) -> list[dict]:
    return await run_in_threadpool(notes_repo.list_notes, user_id)


@router.get("/notes/{note_id}")
async def show(note_id: UUID, user_id: UUID = Depends(get_current_user)) -> dict:
    row = await run_in_threadpool(notes_repo.get_note, user_id, note_id)
    if not row:
        # 404 rather than 403: a 403 would confirm the note exists.
        raise HTTPException(404, "Note not found")
    return row


@router.patch("/notes/{note_id}")
async def update(
    note_id: UUID, request: UpdateNoteRequest, user_id: UUID = Depends(get_current_user)
) -> dict:
    row = await run_in_threadpool(notes_repo.update_note, user_id, note_id, request.note)
    if not row:
        raise HTTPException(404, "Note not found")
    return row


@router.delete("/notes/{note_id}", status_code=204)
async def destroy(note_id: UUID, user_id: UUID = Depends(get_current_user)) -> None:
    if not await run_in_threadpool(notes_repo.delete_note, user_id, note_id):
        raise HTTPException(404, "Note not found")
