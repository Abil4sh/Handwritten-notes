"""Authentication.

Supabase issues a JWT when a user signs in. The frontend sends it on every
request; this module verifies it and produces a user id.

Verification uses JWKS: we fetch Supabase's *public* keys over HTTPS and check
the signature against them. Nothing secret is stored, and key rotation is
handled automatically -- which matters because Supabase projects now sign with
rotating ECC keys rather than one shared secret.

Older projects still sign with a shared HS256 secret. If SUPABASE_JWT_SECRET is
set we fall back to that, so both kinds of project work.
"""

from functools import lru_cache
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient

from app.config import get_settings

bearer = HTTPBearer(auto_error=True)

ASYMMETRIC_ALGORITHMS = ["ES256", "RS256"]
CREDENTIALS_ERROR = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Invalid or expired token",
    headers={"WWW-Authenticate": "Bearer"},
)


@lru_cache(maxsize=1)
def get_jwk_client() -> PyJWKClient:
    url = f"{get_settings().supabase_url}/auth/v1/.well-known/jwks.json"
    # Caching keeps us from fetching the key set on every single request.
    return PyJWKClient(url, cache_keys=True, lifespan=3600)


def decode_token(token: str) -> dict:
    settings = get_settings()

    try:
        signing_key = get_jwk_client().get_signing_key_from_jwt(token)
        return jwt.decode(
            token,
            signing_key.key,
            algorithms=ASYMMETRIC_ALGORITHMS,
            audience="authenticated",
        )
    except jwt.PyJWTError:
        pass
    except Exception:
        # Network trouble reaching JWKS, or a token signed with the legacy
        # shared secret. Fall through to the HS256 path.
        pass

    if settings.supabase_jwt_secret:
        return jwt.decode(
            token,
            settings.supabase_jwt_secret,
            algorithms=["HS256"],
            audience="authenticated",
        )

    raise jwt.InvalidTokenError("no usable verification key")


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer),
) -> UUID:
    """The authenticated user's id, or 401.

    Every database query must filter on this value. FastAPI uses the service
    role key, which bypasses row level security, so this is the only thing
    keeping one user's notes away from another.
    """
    try:
        payload = decode_token(credentials.credentials)
    except Exception:
        raise CREDENTIALS_ERROR

    subject = payload.get("sub")
    if not subject:
        raise CREDENTIALS_ERROR

    try:
        return UUID(subject)
    except ValueError:
        raise CREDENTIALS_ERROR
