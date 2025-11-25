import os
from datetime import timedelta
from app.core.config import settings
from fastapi import Response, Cookie, Header, HTTPException

ACCESS_COOKIE = "access_token"
REFRESH_COOKIE = "refresh_token"
CSRF_COOKIE = "csrf_token"

# Env flags
USE_CROSS_SITE_COOKIES = settings.cross_site_cookies == 1
COOKIE_DOMAIN = settings.cookie_domain  # ej: ".kiwinumslide.com"


def _cookie_params(prod: bool):
    """
    Devuelve (secure, samesite) según el entorno:

    - Si USE_CROSS_SITE_COOKIES=True  -> SameSite=None + Secure=True
      (útil para túneles / dominios distintos, etc.)
    - Si no                           -> SameSite=Lax + Secure=prod
      (para mismo "site", como www/api.kiwinumslide.com en prod)
    """
    # Caso normal: mismo site -> Lax + secure sólo en prod
    secure = prod
    samesite = "Lax"

    # Caso cross-site explícito
    if USE_CROSS_SITE_COOKIES:
        secure = True
        samesite = "None"

    return secure, samesite


def _base_cookie_kwargs(*, prod: bool, httponly: bool, path: str = "/"):
    secure, samesite = _cookie_params(prod)
    kwargs = {
        "httponly": httponly,
        "secure": secure,
        "samesite": samesite,
        "path": path,
    }
    # Si COOKIE_DOMAIN está definido, hacemos que todos los cookies
    # compartan dominio (ej: ".kiwinumslide.com")
    if COOKIE_DOMAIN:
        kwargs["domain"] = COOKIE_DOMAIN
    return kwargs


def set_auth_cookies(response: Response, access: str, refresh: str | None, *, prod: bool):
    """
    Setea access_token y refresh_token como cookies HttpOnly.
    """
    # access_token en path "/"
    access_kwargs = _base_cookie_kwargs(prod=prod, httponly=True, path="/")
    response.set_cookie(
        key=ACCESS_COOKIE,
        value=access,
        max_age=int(timedelta(minutes=15).total_seconds()),
        **access_kwargs,
    )

    # refresh_token en path "/auth"
    if refresh:
        refresh_kwargs = _base_cookie_kwargs(prod=prod, httponly=True, path="/auth")
        response.set_cookie(
            key=REFRESH_COOKIE,
            value=refresh,
            max_age=int(timedelta(days=30).total_seconds()),
            **refresh_kwargs,
        )


def set_csrf_cookie(response: Response, token: str, *, prod: bool):
    """
    Setea csrf_token como cookie legible por JS (no HttpOnly)
    para que el frontend pueda mandarlo en el header X-CSRF-Token.
    """
    csrf_kwargs = _base_cookie_kwargs(prod=prod, httponly=False, path="/")
    response.set_cookie(
        key=CSRF_COOKIE,
        value=token,
        max_age=int(timedelta(days=7).total_seconds()),
        **csrf_kwargs,
    )


def clear_auth_cookies(response: Response, *, prod: bool):
    """
    Elimina access_token, refresh_token y csrf_token usando
    los mismos dominios/paths que se usaron al crearlos.
    """
    secure, samesite = _cookie_params(prod)

    base_delete = {
        "secure": secure,
        "samesite": samesite,
    }
    if COOKIE_DOMAIN:
        base_delete["domain"] = COOKIE_DOMAIN

    # access_token (path '/')
    response.delete_cookie(
        ACCESS_COOKIE,
        path="/",
        **base_delete,
    )

    # refresh_token: bórralo en ambos paths por si cambió en alguna versión
    response.delete_cookie(
        REFRESH_COOKIE,
        path="/auth",
        **base_delete,
    )
    response.delete_cookie(
        REFRESH_COOKIE,
        path="/",
        **base_delete,
    )

    # csrf_token
    response.delete_cookie(
        CSRF_COOKIE,
        path="/",
        **base_delete,
    )


def require_csrf(
    csrf_header: str | None = Header(default=None, alias="X-CSRF-Token"),
    csrf_cookie: str | None = Cookie(default=None, alias=CSRF_COOKIE),
):
    """
    Valida que el header X-CSRF-Token coincida con la cookie csrf_token.

    - Si USE_CROSS_SITE_COOKIES=True (CROSS_SITE_COOKIES=1) -> se salta la validación.
      Útil para desarrollo local con túneles / dominios raros.
    - Si no -> exige que header y cookie existan y sean iguales.
    """
    # Modo "relajado" para desarrollo / túneles
    if USE_CROSS_SITE_COOKIES:
        return

    # Modo estricto (producción normal)
    if not csrf_header or not csrf_cookie or csrf_header != csrf_cookie:
        raise HTTPException(status_code=403, detail="CSRF validation failed")
