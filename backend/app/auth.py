"""Authentication dependency for Supabase Auth access tokens."""

from __future__ import annotations

from dataclasses import dataclass
import time
from uuid import UUID

import httpx
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer


bearer = HTTPBearer(auto_error=False)
_jwks_cache: dict[str, tuple[float, dict[str, dict]]] = {}


@dataclass(frozen=True, slots=True)
class UserIdentity:
    user_id: UUID
    email: str | None


async def _jwks_signing_key(token: str, url: str):
    import jwt

    header = jwt.get_unverified_header(token)
    if header.get("alg") != "ES256" or not isinstance(header.get("kid"), str):
        raise jwt.InvalidTokenError("JWT algorithm or key id is not allowed")
    kid = header["kid"]
    cached = _jwks_cache.get(url)
    if cached is None or cached[0] <= time.monotonic() or kid not in cached[1]:
        async with httpx.AsyncClient(timeout=5.0, follow_redirects=False) as client:
            response = await client.get(url)
            response.raise_for_status()
            payload = response.json()
        keys = payload.get("keys")
        if not isinstance(keys, list):
            raise jwt.InvalidTokenError("JWKS response has no keys")
        key_map = {key["kid"]: key for key in keys if isinstance(key, dict) and isinstance(key.get("kid"), str)}
        _jwks_cache[url] = (time.monotonic() + 300, key_map)
        cached = _jwks_cache[url]
    jwk = cached[1].get(kid)
    if jwk is None:
        raise jwt.InvalidTokenError("JWT signing key not found")
    return jwt.PyJWK.from_dict(jwk).key


async def current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> UserIdentity:
    settings = request.app.state.settings
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "authentication required", headers={"WWW-Authenticate": "Bearer"})
    if not settings.jwt_secret and not settings.jwks_url:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "authentication is not configured")
    try:
        import jwt
        from jwt.exceptions import PyJWTError
    except ImportError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "PyJWT is not installed") from exc
    try:
        issuer = f"{settings.supabase_url}/auth/v1" if settings.supabase_url else None
        if settings.jwt_secret:
            claims = jwt.decode(
                credentials.credentials,
                settings.jwt_secret,
                algorithms=["HS256"],
                audience="authenticated",
                issuer=issuer,
            )
        else:
            signing_key = await _jwks_signing_key(credentials.credentials, settings.jwks_url)
            claims = jwt.decode(
                credentials.credentials,
                signing_key,
                algorithms=["ES256"],
                audience="authenticated",
                issuer=issuer,
            )
        user_id = UUID(str(claims["sub"]))
    except (PyJWTError, KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid access token", headers={"WWW-Authenticate": "Bearer"}) from exc
    return UserIdentity(user_id=user_id, email=claims.get("email"))
