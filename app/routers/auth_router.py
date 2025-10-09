import jwt
from fastapi import APIRouter, HTTPException, Depends

from ..core import security
from ..repositories import users_repo
from ..schemas.auth_schema import RegisterIn, UserOut, VerifyEmailIn, LoginOut, LoginIn, RefreshOut, RefreshIn
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
def login(body: LoginIn):
    result = auth_service.login_user(body.email, body.password)
    return {
        "access_token": result["access_token"],
        "refresh_token": result["refresh_token"],
        "token_type": "bearer",
        "user": result["user"],
        "needs_verification": result["needs_verification"],
    }


@router.post("/refresh")
def refresh_token_route(body: RefreshIn):   # RefreshIn: { refresh_token: str }
    try:
        data = security.decode_token(body.refresh_token)
        security.require_token_type(data, "refresh")
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Refresh token expired")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    user_id = int(data["sub"])
    email   = data["email"]

    # (Opcional) revisa en DB que el user siga activo, no bloqueado, etc.

    new_access  = security.create_access_token(user_id, email)
    # (Opcional) rotación:
    # new_refresh = security.create_refresh_token(user_id, email)

    return {
        "access_token": new_access,
        "token_type": "bearer",
        # "refresh_token": new_refresh,   # si implementas rotación
    }



@router.get("/me", response_model=UserOut)
def read_me(token_data: dict = Depends(security.get_current_token)):
    """
    Endpoint protegido: requiere Authorization: Bearer <access_token>.
    """
    user_id = int(token_data["sub"])
    user = users_repo.get_user_by_id(user_id)
    # adapta a tu repo: users_repo.get_user_by_id debe existir; si no, crea una función similar
    return {
        "id": user["id"],
        "name": user["name"],
        "email": user["email"],
        "is_verified": bool(user["is_verified"]),
    }