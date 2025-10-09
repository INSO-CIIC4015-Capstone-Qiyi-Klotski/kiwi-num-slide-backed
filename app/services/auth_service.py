import os
from urllib.parse import urlencode

import jwt
from botocore.exceptions import ClientError
from fastapi import HTTPException, status
from passlib.hash import bcrypt

from ..core import security
from ..core.security import create_verify_token, decode_token
from ..repositories import users_repo
from ..services.email_services import send_simple_email, SES_SENDER_EMAIL, AWS_REGION

PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL")

def register_user(name: str, email: str, password: str) -> dict:
    existing = users_repo.get_user_by_email(email)
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    hashed = bcrypt.hash(password)
    user = users_repo.insert_user(name, email, hashed)
    user["verify_token"] = create_verify_token(user["id"], user["email"], minutes=60)
    return user


def send_verification_email(email: str) -> dict:
    user = users_repo.get_user_by_email(email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user["is_verified"]:
        return {"ok": True, "message": "User already verified"}

    token = create_verify_token(user["id"], user["email"], minutes=60)
    verify_url = f"{PUBLIC_BASE_URL}/auth/verify/confirm?token={token}"

    subject = "Verify your KiwiNumSlide account"
    html = f"""
        <h3>Verify your KiwiNumSlide account</h3>
        <p>Click to verify your email:</p>
        <p><a href="{verify_url}">{verify_url}</a></p>
        <p>If you didn’t request this, you can ignore this message.</p>
    """

    msg_id = send_simple_email(to_email=email, subject=subject, html_body=html)
    return {"ok": True, "message": "Verification email sent", "message_id": msg_id}



def verify_account_by_token(token: str) -> dict:
    try:
        payload = decode_token(token)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid token")

    if payload.get("typ") != "verify":
        raise HTTPException(status_code=400, detail="Invalid token type")

    user_id = int(payload["sub"])
    user = users_repo.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user["is_verified"]:
        return {"ok": True}

    users_repo.mark_verified(user_id)
    return {"ok": True}



def login_user(email: str, password: str):
    user = users_repo.get_user_by_email(email)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    if not security.verify_password(password, user["password_hash"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    access_token = security.create_access_token(
        user_id=user["id"],
        email=user["email"]
    )

    refresh_token = security.create_refresh_token(
        user_id=user["id"],
        email=user["email"]
    )

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "user": {
            "id": user["id"],
            "name": user["name"],
            "email": user["email"],
            "is_verified": bool(user["is_verified"]),
        },
        "needs_verification": not bool(user["is_verified"]),
    }


def refresh_access_token(refresh_token: str):
    try:
        data = security.decode_token(refresh_token)
        security.require_token_type(data, "refresh")
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    email = data.get("email")
    if not email:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token payload")

    user = users_repo.get_user_by_email(email)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    new_access = security.create_access_token(user_id=user["id"], email=user["email"])


    return {"access_token": new_access, "refresh_token": None}