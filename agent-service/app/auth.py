"""JWT verification. The secret and claim names must match the Next.js session token."""
import jwt
from fastapi import Header, HTTPException, Request

from . import config


def current_user(request: Request, authorization: str | None = Header(default=None),
                 x_dev_role: str | None = Header(default=None)) -> dict:
    if config.AUTH_DISABLED:
        role = x_dev_role or "technician"
        return {"sub": f"dev-{role}", "role": role}
    token = None
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:]
    token = token or request.cookies.get(config.AUTH_COOKIE_NAME)
    if not token:
        raise HTTPException(401, "Not authenticated")
    try:
        claims = jwt.decode(token, config.AUTH_SECRET, algorithms=["HS256"])
    except jwt.PyJWTError:
        raise HTTPException(401, "Invalid or expired token")
    if claims.get("role") not in ("customer", "technician"):
        raise HTTPException(403, "Unknown role")
    return claims
