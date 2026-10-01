from fastapi import APIRouter, Depends

from app.api.deps import Actor, DbSession, get_current_admin
from app.schemas.timekeeping import DeviceIn, DeviceOut, DeviceWithToken
from app.services import device_service

router = APIRouter(
    prefix="/devices", tags=["dispositivos"], dependencies=[Depends(get_current_admin)]
)


def _with_token(device: object, token: str) -> DeviceWithToken:
    return DeviceWithToken.model_validate(
        {**DeviceOut.model_validate(device).model_dump(), "token": token}
    )


@router.get("", response_model=list[DeviceOut])
def list_devices(db: DbSession) -> list[DeviceOut]:
    return [DeviceOut.model_validate(d) for d in device_service.list_devices(db)]


@router.post("", response_model=DeviceWithToken, status_code=201)
def create_device(data: DeviceIn, db: DbSession, actor: Actor) -> DeviceWithToken:
    device, token = device_service.create(db, data.name, actor)
    return _with_token(device, token)


@router.post("/{device_id}/rotate-token", response_model=DeviceWithToken)
def rotate_token(device_id: int, db: DbSession, actor: Actor) -> DeviceWithToken:
    device, token = device_service.rotate_token(db, device_id, actor)
    return _with_token(device, token)


@router.post("/{device_id}/activate", response_model=DeviceOut)
def activate_device(device_id: int, db: DbSession, actor: Actor) -> DeviceOut:
    return DeviceOut.model_validate(device_service.set_active(db, device_id, True, actor))


@router.post("/{device_id}/deactivate", response_model=DeviceOut)
def deactivate_device(device_id: int, db: DbSession, actor: Actor) -> DeviceOut:
    return DeviceOut.model_validate(device_service.set_active(db, device_id, False, actor))
