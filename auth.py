import os
from fastapi import Request, HTTPException
from starlette.middleware.sessions import SessionMiddleware

ALLOWED_DOMAIN = os.getenv("ALLOWED_DOMAIN")
ADMIN_EMAILS = os.getenv("ADMIN_EMAILS", "").split(",")

def require_login(request: Request):

    user = request.session.get("user")

    if not user:
        raise HTTPException(status_code=401, detail="Login required")

    return user


def require_admin(request: Request):

    user = require_login(request)

    if user["email"] not in ADMIN_EMAILS:
        raise HTTPException(status_code=403, detail="Admin access only")

    return user

