from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.clock import now_utc
from app.core.errors import not_found
from app.core.security import new_opaque_token, sha256_hex
from app.models import Device
from app.services import audit


def _snapshot(d: Device) -> dict[str, object]:
    return {"name": d.name, "is_active": d.is_active}


def list_devices(db: Session) -> list[Device]:
    return list(db.scalars(select(Device).order_by(Device.name, Device.id)).all())


def get(db: Session, device_id: int) -> Device:
    device = db.get(Device, device_id)
    if device is None:
        raise not_found("Dispositivo não encontrado.")
    return device


def create(db: Session, name: str, actor: audit.Actor) -> tuple[Device, str]:
    """Cadastra o terminal. O token devolvido é exibido uma única vez."""
    token = new_opaque_token()
    device = Device(name=name, token_hash=sha256_hex(token))
    db.add(device)
    db.flush()
    audit.record(
        db,
        actor=actor,
        action="device.create",
        entity_type="device",
        entity_id=device.id,
        after=_snapshot(device),
    )
    db.commit()
    return device, token


def rotate_token(db: Session, device_id: int, actor: audit.Actor) -> tuple[Device, str]:
    device = get(db, device_id)
    token = new_opaque_token()
    device.token_hash = sha256_hex(token)
    audit.record(
        db, actor=actor, action="device.rotate_token", entity_type="device", entity_id=device.id
    )
    db.commit()
    return device, token


def set_active(db: Session, device_id: int, active: bool, actor: audit.Actor) -> Device:
    device = get(db, device_id)
    if device.is_active != active:
        before = _snapshot(device)
        device.is_active = active
        audit.record(
            db,
            actor=actor,
            action="device.activate" if active else "device.deactivate",
            entity_type="device",
            entity_id=device.id,
            before=before,
            after=_snapshot(device),
        )
        db.commit()
    return device


def authenticate(db: Session, token: str) -> Device | None:
    device = db.scalar(select(Device).where(Device.token_hash == sha256_hex(token)))
    if device is None or not device.is_active:
        return None
    device.last_seen_at = now_utc()
    db.commit()
    return device
