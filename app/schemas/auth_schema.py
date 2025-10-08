from pydantic import BaseModel, EmailStr, Field


# ===== Inputs =====
class RegisterIn(BaseModel):
    name: str = Field(min_length=2)
    email: EmailStr
    password: str = Field(min_length=8)


class VerifyEmailIn(BaseModel):
    email: EmailStr


class VerifyTokenIn(BaseModel):
    token: str


class LoginIn(BaseModel):
    email: EmailStr
    password: str


# ===== Outputs =====
class UserOut(BaseModel):
    id: int
    name: str
    email: EmailStr
    is_verified: bool


class VerifyOut(BaseModel):
    ok: bool


class LoginOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut
    needs_verification: bool

