import jwt
from fastapi import APIRouter, HTTPException, Depends, Response, Request, Cookie


from ..core import security
from ..core.cookies import set_auth_cookies, set_csrf_cookie, REFRESH_COOKIE, clear_auth_cookies, require_csrf
from ..core.security import get_current_token_cookie_or_header, get_current_token_optional_cookie_or_header
from ..repositories import users_repo
from ..schemas.auth_schema import RegisterIn, UserOut, VerifyEmailIn, LoginOut, LoginIn, RefreshOut, RefreshIn, \
    StatusOut
from ..services import auth_service
from fastapi import Query

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserOut, status_code=201)
def register(body: RegisterIn):
    user = auth_service.register_user(body.name, body.email, body.password)
    return user


@router.post("/verify", status_code=200)
def send_verification_email(body: VerifyEmailIn):
    result = auth_service.send_verification_email(body.email)
    return result


@router.get("/verify/confirm")
def confirm_verification_via_get(token: str = Query(...)):
    result = auth_service.verify_account_by_token(token)
    return {"ok": True, "message": "Email verified successfully"}


@router.post("/login", response_model=LoginOut)
def login(body: LoginIn, response: Response, request: Request):
    """
    Login tradicional: devuelve JSON como antes
    **y** ahora además setea cookies HttpOnly (access/refresh) y csrf.
    """
    result = auth_service.login_user(body.email, body.password)

    prod = request.url.scheme == "https"
    set_auth_cookies(response, result["access_token"], result["refresh_token"], prod=prod)
    # Puedes usar un token aleatorio firmado. Aquí, para demo, algo estable:
    set_csrf_cookie(response, token="csrf-" + result["user"]["email"], prod=prod)

    return {
        "access_token": result["access_token"],
        "refresh_token": result["refresh_token"],
        "token_type": "bearer",
        "user": result["user"],
        "needs_verification": result["needs_verification"],
    }


@router.post("/refresh", response_model=RefreshOut)
def refresh_token_route(
    response: Response,
    request: Request,
    body: RefreshIn | None = None,
    refresh_cookie: str | None = Cookie(default=None, alias=REFRESH_COOKIE),
    _csrf = Depends(require_csrf),
):
    """
    Refresca usando:
    - Preferentemente la cookie HttpOnly 'refresh_token'
    - Como fallback, acepta el body {refresh_token} para compatibilidad.
    """
    refresh_token = refresh_cookie or (body.refresh_token if body else None)
    if not refresh_token:
        raise HTTPException(status_code=401, detail="Missing refresh token")

    try:
        data = security.decode_token(refresh_token)
        security.require_token_type(data, "refresh")
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Refresh token expired")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    user_id = int(data["sub"])
    email = data["email"]

    new_access = security.create_access_token(user_id, email)
    # Si rotas refresh, créalo aquí y vuelve a setearlo

    set_auth_cookies(response, new_access, None, prod=(request.url.scheme == "https"))
    return {"access_token": new_access, "token_type": "bearer"}


@router.post("/logout")
def logout(response: Response, request: Request):
    clear_auth_cookies(response, prod=(request.url.scheme == "https"))
    return {"ok": True}



@router.get("/me", response_model=UserOut)
def read_me(token_data: dict = Depends(security.get_current_token_cookie_or_header)):
    """
    Protegido: ahora acepta Authorization: Bearer ... **o** cookie 'access_token'.
    """
    user_id = int(token_data["sub"])
    user = users_repo.get_user_by_id(user_id)
    return {
        "id": user["id"],
        "name": user["name"],
        "email": user["email"],
        "is_verified": bool(user["is_verified"]),
    }


@router.get("/status", response_model=StatusOut)
def auth_status(token_data: dict | None = Depends(get_current_token_optional_cookie_or_header)):
    """
    Si hay access token válido (header o cookie) -> { verified, user }.
    Si no -> { verified: False, user: None }.
    """
    if not token_data:
        return {"verified": False, "user": None}

    user_id = int(token_data["sub"])
    user = users_repo.get_user_by_id(user_id)
    if not user:
        return {"verified": False, "user": None}

    return {
        "verified": bool(user["is_verified"]),
        "user": {
            "id": user["id"],
            "name": user["name"],
            "email": user["email"],
            "is_verified": bool(user["is_verified"]),
        },
    }