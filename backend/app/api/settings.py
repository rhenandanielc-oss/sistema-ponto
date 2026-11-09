from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.api.deps import Actor, DbSession, get_current_admin
from app.services import location_service, settings_service
from app.services.settings_service import CompanySettings, CompanySettingsUpdate

router = APIRouter(
    prefix="/settings", tags=["configurações"], dependencies=[Depends(get_current_admin)]
)


@router.get("", response_model=CompanySettings)
def get_settings(db: DbSession) -> CompanySettings:
    return settings_service.load(db)


@router.patch("", response_model=CompanySettings)
def update_settings(data: CompanySettingsUpdate, db: DbSession, actor: Actor) -> CompanySettings:
    return settings_service.update(db, data, actor)


class LocateIn(BaseModel):
    query: str = Field(
        min_length=3, max_length=500, description="Endereço, link do Google Maps ou 'lat, lng'"
    )


class LocateOut(BaseModel):
    latitude: float
    longitude: float
    label: str


@router.post("/locate", response_model=LocateOut)
def locate(data: LocateIn) -> LocateOut:
    """Acha o local do restaurante por endereço, link do Maps ou coordenadas (não grava nada)."""
    found = location_service.locate(data.query)
    return LocateOut(latitude=found.latitude, longitude=found.longitude, label=found.label)
