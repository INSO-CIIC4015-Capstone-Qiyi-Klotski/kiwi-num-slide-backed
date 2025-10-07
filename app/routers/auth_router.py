from fastapi import APIRouter
from ..schemas.auth_schema import RegisterIn, UserOut
from ..services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserOut, status_code=201)
def register(body: RegisterIn):
    user = auth_service.register_user(body.name, body.email, body.password)
    return user
