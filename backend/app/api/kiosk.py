from fastapi import APIRouter
from pydantic import BaseModel

from app.api.deps import CurrentDevice
from app.core.clock import now_utc
from app.schemas.common import LocalDatetime

router = APIRouter(prefix="/kiosk", tags=["kiosk"])


class PingOut(BaseModel):
    device: str
    server_time: LocalDatetime


@router.get("/ping", response_model=PingOut)
def ping(device: CurrentDevice) -> PingOut:
    """Confirma que o terminal está autorizado e devolve o horário do servidor para exibição."""
    return PingOut(device=device.name, server_time=now_utc())
