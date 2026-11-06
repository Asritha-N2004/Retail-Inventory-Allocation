import os, secrets, time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
import jwt
from pwdlib import PasswordHash
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from .database import Session, User

passwords = PasswordHash.recommended()
secret = os.getenv("JWT_SECRET") or secrets.token_hex(32)
if os.getenv("VERCEL") and not os.getenv("JWT_SECRET"):
    raise RuntimeError("Set a stable JWT_SECRET before deploying to Vercel")
bearer = HTTPBearer()
attempts = defaultdict(deque)


def token(user):
    return jwt.encode(
        {"sub": str(user.id), "exp": datetime.now(timezone.utc) + timedelta(hours=8)},
        secret,
        algorithm="HS256",
    )


def current_user(credentials: HTTPAuthorizationCredentials = Depends(bearer)):
    try:
        claims = jwt.decode(credentials.credentials, secret, algorithms=["HS256"])
        with Session() as s:
            user = s.get(User, int(claims["sub"]))
        if not user:
            raise ValueError("Unknown user")
        return user
    except (jwt.PyJWTError, ValueError, KeyError):
        raise HTTPException(401, "Invalid or expired token")


def manager(user=Depends(current_user)):
    if user.role not in ["Administrator", "Inventory Manager"]:
        raise HTTPException(403, "Inventory manager permission required")
    return user


def administrator(user=Depends(current_user)):
    if user.role != "Administrator":
        raise HTTPException(403, "Administrator permission required")
    return user


def throttle(key):
    q = attempts[key]
    while q and q[0] < time.monotonic() - 60:
        q.popleft()
    if len(q) >= 10:
        raise HTTPException(429, "Too many login attempts; retry in one minute")
    q.append(time.monotonic())
