import os
from datetime import timedelta
from fastapi import Response, Cookie, Header, HTTPException

ACCESS_COOKIE = "access_token"
REFRESH_COOKIE = "refresh_token"
CSRF_COOKIE = "csrf_token"
USE_CROSS_SITE_COOKIES = os.getenv("CROSS_SITE_COOKIES", "0")

def _cookie_params(prod: bool):
    """
    Devuelve (secure, samesite) según el entorno:

    - Si USE_CROSS_SITE_COOKIES=1  -> SameSite=None + Secure=True (para túneles / dominios distintos)
    - Si no                        -> SameSite=Lax + Secure=prod (para mismo dominio en prod)
    """
    if USE_CROSS_SITE_COOKIES:
        return True, "None"
    else:
        # En un deploy "normal" mismo dominio, Lax es suficiente
        return prod, "Lax"

def set_auth_cookies(response: Response, access: str, refresh: str | None, *, prod: bool):
    secure, samesite = _cookie_params(prod)

    response.set_cookie(
        key=ACCESS_COOKIE, value=access,
        httponly=True, secure=secure,
        samesite=samesite,
        max_age=int(timedelta(minutes=15).total_seconds()),
        path="/"
    )
    if refresh:
        response.set_cookie(
            key=REFRESH_COOKIE, value=refresh,
            httponly=True, secure=secure,
            samesite=samesite,
            max_age=int(timedelta(days=30).total_seconds()),
            path="/auth"
        )


def set_csrf_cookie(response: Response, token: str, *, prod: bool):
    response.set_cookie(
        key=CSRF_COOKIE, value=token,
        httponly=False, secure=prod,
        samesite="None" if prod else "Lax",
        max_age=int(timedelta(days=7).total_seconds()),
        path="/"
    )


def clear_auth_cookies(response: Response, *, prod: bool):
    secure, samesite = _cookie_params(prod)

    # access_token (path '/')
    response.delete_cookie("access_token", path="/", samesite=samesite)

    # refresh_token: bórralo en ambos paths por si cambió en alguna versión
    response.delete_cookie("refresh_token", path="/auth", samesite=samesite)
    response.delete_cookie("refresh_token", path="/", samesite=samesite)

    # csrf
    response.delete_cookie("csrf_token", path="/", samesite=samesite)


def require_csrf(
    csrf_header: str | None = Header(default=None, alias="X-CSRF-Token"),
    csrf_cookie: str | None = Cookie(default=None, alias=CSRF_COOKIE)
):
    if not csrf_header or not csrf_cookie or csrf_header != csrf_cookie:
        raise HTTPException(status_code=403, detail="CSRF validation failed")
