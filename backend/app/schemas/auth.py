from pydantic import BaseModel, EmailStr

from app.schemas.common import LocalDatetime, ORMModel


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class AdminOut(ORMModel):
    id: int
    email: str
    name: str
    is_active: bool
    last_login_at: LocalDatetime | None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    admin: AdminOut
