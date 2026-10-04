from datetime import date as Date
from typing import Annotated

from pydantic import BaseModel, Field, model_validator

from app.schemas.common import LocalDatetime, ORMModel

Cents = Annotated[int, Field(gt=0, le=10_000_000, description="Valor em centavos (R$ 6,00 = 600)")]
Name = Annotated[str, Field(min_length=1, max_length=120)]


class ConsumptionItemIn(BaseModel):
    name: Name
    price_cents: Cents


class ConsumptionItemUpdate(BaseModel):
    name: Name | None = None
    price_cents: Cents | None = None
    is_active: bool | None = None


class ConsumptionItemOut(ORMModel):
    id: int
    name: str
    price_cents: int
    is_active: bool


class ConsumptionEntryIn(BaseModel):
    """Um item cadastrado (`item_id`) ou um consumo avulso (`description` + `unit_price_cents`)."""

    item_id: int | None = None
    description: Name | None = None
    unit_price_cents: Cents | None = None
    quantity: int = Field(default=1, ge=1, le=1000)
    entry_date: Date | None = Field(default=None, description="Padrão: hoje")

    @model_validator(mode="after")
    def _item_or_free(self) -> "ConsumptionEntryIn":
        by_item = (
            self.item_id is not None and self.description is None and self.unit_price_cents is None
        )
        free = (
            self.item_id is None
            and self.description is not None
            and self.unit_price_cents is not None
        )
        if by_item or free:
            return self
        raise ValueError("Informe item_id ou (description e unit_price_cents), não os dois.")


class ConsumptionCancelIn(BaseModel):
    reason: Annotated[str, Field(min_length=3, max_length=500)]


class ConsumptionEntryOut(ORMModel):
    id: int
    employee_id: int
    entry_date: Date
    item_id: int | None
    description: str
    quantity: int
    unit_price_cents: int
    total_cents: int
    created_at: LocalDatetime
    canceled_at: LocalDatetime | None
    cancel_reason: str | None


class ConsumptionList(BaseModel):
    items: list[ConsumptionEntryOut]
    total_cents: int = Field(description="Soma dos lançamentos não cancelados do período")
