from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.deps import CurrentDevice
from app.core.clock import now_utc
from app.core.rate_limit import rate_limit
from app.schemas.common import LocalDatetime

# O limite vem antes da autenticação: tokens inválidos também contam.
router = APIRouter(
    prefix="/kiosk", tags=["kiosk"], dependencies=[Depends(rate_limit("kiosk", limit=120))]
)


class PingOut(BaseModel):
    device: str
    server_time: LocalDatetime


@router.get("/ping", response_model=PingOut)
def ping(device: CurrentDevice) -> PingOut:
    """Confirma que o terminal está autorizado e devolve o horário do servidor para exibição."""
    return PingOut(device=device.name, server_time=now_utc())
