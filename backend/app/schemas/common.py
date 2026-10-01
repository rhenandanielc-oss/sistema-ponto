from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, PlainSerializer

from app.core.config import get_settings


def _to_company_tz(value: datetime) -> str:
    return value.astimezone(get_settings().tz).isoformat()


# Instantes são guardados em UTC e devolvidos no fuso da empresa (ex.: 2026-09-01T08:02:13-03:00).
LocalDatetime = Annotated[
    datetime, PlainSerializer(_to_company_tz, return_type=str, when_used="json")
]


class Page[T](BaseModel):
    items: list[T]
    page: int
    page_size: int
    total: int


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)
