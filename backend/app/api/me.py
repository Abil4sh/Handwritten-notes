"""A protected endpoint, used to prove authentication works."""

from uuid import UUID

from fastapi import APIRouter, Depends

from app.auth.dependencies import get_current_user

router = APIRouter(tags=["auth"])


@router.get("/me")
async def me(user_id: UUID = Depends(get_current_user)) -> dict:
    return {"user_id": str(user_id)}
