"""Note structuring endpoint.

Raw text in, structured Note out. No database yet -- the note is returned to
the caller rather than saved.
"""

from fastapi import APIRouter
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from app.notes.schema import Note
from app.notes.structure import structure_note

router = APIRouter(tags=["notes"])

MAX_INPUT_CHARS = 8000


class StructureRequest(BaseModel):
    raw_text: str = Field(min_length=1, max_length=MAX_INPUT_CHARS)


@router.post("/notes/structure")
async def structure(request: StructureRequest) -> Note:
    return await run_in_threadpool(structure_note, request.raw_text)
