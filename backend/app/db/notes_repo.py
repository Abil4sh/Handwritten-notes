"""Note persistence.

EVERY function takes user_id and filters on it. FastAPI connects with the
service role key, which bypasses row level security, so this filter is the
only thing separating one user's notes from another's. A missing .eq() here
is a data leak, not a bug the database will catch.

Reads return None rather than raising when a row is absent or owned by someone
else -- the API turns that into a 404, which does not reveal whether the id
exists.
"""

from uuid import UUID

from app.db.client import get_client
from app.db.hashing import content_hash
from app.notes.schema import Note

TABLE = "notes"
FIELDS = "id,title,source_type,content,content_hash,created_at,updated_at"


def create_note(user_id: UUID, note: Note, source_text: str | None) -> dict:
    content = note.model_dump()
    row = {
        "user_id": str(user_id),
        "title": note.title,
        "source_type": "text",
        "source_text": source_text,
        "content": content,
        "content_hash": content_hash(content),
    }
    result = get_client().table(TABLE).insert(row).execute()
    return result.data[0]


def list_notes(user_id: UUID, limit: int = 50) -> list[dict]:
    result = (
        get_client()
        .table(TABLE)
        .select("id,title,created_at,updated_at")
        .eq("user_id", str(user_id))
        .order("updated_at", desc=True)
        .limit(limit)
        .execute()
    )
    return result.data


def get_note(user_id: UUID, note_id: UUID) -> dict | None:
    result = (
        get_client()
        .table(TABLE)
        .select(FIELDS)
        .eq("id", str(note_id))
        .eq("user_id", str(user_id))
        .execute()
    )
    return result.data[0] if result.data else None


def update_note(user_id: UUID, note_id: UUID, note: Note) -> dict | None:
    content = note.model_dump()
    result = (
        get_client()
        .table(TABLE)
        .update(
            {
                "title": note.title,
                "content": content,
                "content_hash": content_hash(content),
            }
        )
        .eq("id", str(note_id))
        .eq("user_id", str(user_id))
        .execute()
    )
    return result.data[0] if result.data else None


def delete_note(user_id: UUID, note_id: UUID) -> bool:
    result = (
        get_client()
        .table(TABLE)
        .delete()
        .eq("id", str(note_id))
        .eq("user_id", str(user_id))
        .execute()
    )
    return bool(result.data)
