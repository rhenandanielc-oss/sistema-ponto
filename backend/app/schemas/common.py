from pydantic import BaseModel, ConfigDict


class Page[T](BaseModel):
    items: list[T]
    page: int
    page_size: int
    total: int


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)
