"""Endpoints listing what the renderer can do.

The frontend calls these to build its option chips, so adding a template or a
paper shows up in the UI without any frontend change.
"""

from fastapi import APIRouter

from app.config import get_settings
from app.render.handwriting import load_styles
from app.render.paper import load_papers
from app.render.template import load_templates

router = APIRouter(tags=["options"])


@router.get("/templates")
def list_templates() -> list[dict]:
    return [{"id": t["id"], "name": t["name"]} for t in load_templates().values()]


@router.get("/handwriting-styles")
def list_styles() -> list[dict]:
    return [
        {"id": s.id, "name": s.name, "font_id": s.font_id}
        for s in load_styles().values()
    ]


@router.get("/papers")
def list_papers() -> list[dict]:
    return [{"id": p.id, "name": p.name} for p in load_papers().values()]


@router.get("/config")
def public_config() -> dict:
    """Values the browser needs. Only ever the anon key -- never the service key."""
    settings = get_settings()
    return {
        "supabase_url": settings.supabase_url,
        "supabase_anon_key": settings.supabase_anon_key,
        "auth_enabled": bool(settings.supabase_url and settings.supabase_anon_key),
    }
