from fastapi import APIRouter
from ..schemas.auth_schema import RegisterIn, UserOut, VerifyEmailIn, LoginOut, LoginIn
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
        "token_type": "bearer",
        "user": result["user"],
        "needs_verification": result["needs_verification"],
    }
