"""Render records and PDF storage.

Renders are derived data: they can always be rebuilt from a note. That is why
they are content addressed and safe to delete.
"""

from uuid import UUID

from app.config import get_settings
from app.db.client import get_client

TABLE = "renders"
SIGNED_URL_SECONDS = 900


def find_cached(user_id: UUID, note_id: UUID, spec_hash: str) -> dict | None:
    result = (
        get_client()
        .table(TABLE)
        .select("*")
        .eq("user_id", str(user_id))
        .eq("note_id", str(note_id))
        .eq("spec_hash", spec_hash)
        .eq("status", "done")
        .execute()
    )
    return result.data[0] if result.data else None


def get_render(user_id: UUID, render_id: UUID) -> dict | None:
    result = (
        get_client()
        .table(TABLE)
        .select("*")
        .eq("id", str(render_id))
        .eq("user_id", str(user_id))
        .execute()
    )
    return result.data[0] if result.data else None


def store_render(
    user_id: UUID, note_id: UUID, spec: dict, spec_hash: str, pdf: bytes, pages: int
) -> dict:
    settings = get_settings()
    client = get_client()

    row = (
        client.table(TABLE)
        .insert(
            {
                "user_id": str(user_id),
                "note_id": str(note_id),
                "spec": spec,
                "spec_hash": spec_hash,
                "status": "running",
            }
        )
        .execute()
        .data[0]
    )

    # user_id first in the path so a whole user can be deleted with one prefix
    # sweep, and so a storage policy could restrict by prefix later.
    path = f"{user_id}/{note_id}/{row['id']}.pdf"

    try:
        client.storage.from_(settings.renders_bucket).upload(
            path, pdf, {"content-type": "application/pdf", "upsert": "true"}
        )
    except Exception as exc:
        client.table(TABLE).update({"status": "failed", "error": str(exc)[:400]}).eq(
            "id", row["id"]
        ).execute()
        raise

    return (
        client.table(TABLE)
        .update({"status": "done", "storage_path": path, "page_count": pages})
        .eq("id", row["id"])
        .execute()
        .data[0]
    )


def signed_url(storage_path: str) -> str:
    """Short-lived URL. Never stored in the database -- it expires."""
    response = get_client().storage.from_(get_settings().renders_bucket).create_signed_url(
        storage_path, SIGNED_URL_SECONDS
    )
    return response["signedURL"]
