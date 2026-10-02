from fastapi import APIRouter, Depends

from app.api.deps import Actor, DbSession, get_current_admin
from app.services import settings_service
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
