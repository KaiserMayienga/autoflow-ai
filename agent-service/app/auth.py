"""Verifies the short-lived service token minted by the Next.js server (lib/agent.ts).

Claims: sub = user id (string), role = "customer" | "technician". Browser cookies are
never sent here; Next.js validates the session first, then calls this service.
"""
import jwt
from fastapi import Header, HTTPException

from . import config


def current_user(authorization: str | None = Header(default=None),
                 x_dev_role: str | None = Header(default=None)) -> dict:
    if config.AUTH_DISABLED:
        role = x_dev_role if x_dev_role in ("customer", "technician") else "technician"
        return {"sub": f"dev-{role}", "role": role}
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "Not authenticated")
    try:
        claims = jwt.decode(authorization[7:], config.AGENT_SERVICE_SECRET, algorithms=["HS256"],
                            options={"require": ["exp", "sub"]})
    except jwt.PyJWTError:
        raise HTTPException(401, "Invalid or expired token")
    if claims.get("role") not in ("customer", "technician"):
        raise HTTPException(403, "Unknown role")
    return claims
