from pydantic import BaseModel, EmailStr, Field, field_validator

from app.core.security import MIN_PASSWORD_LENGTH


def _strip_required(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("não pode ficar vazio")
    return value


class AdminCreate(BaseModel):
    email: EmailStr
    name: str = Field(max_length=200)
    password: str = Field(min_length=MIN_PASSWORD_LENGTH, max_length=256)

    _name = field_validator("name")(_strip_required)


class AdminUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=200)
    password: str | None = Field(default=None, min_length=MIN_PASSWORD_LENGTH, max_length=256)

    @field_validator("name")
    @classmethod
    def _name(cls, value: str | None) -> str | None:
        return None if value is None else _strip_required(value)
