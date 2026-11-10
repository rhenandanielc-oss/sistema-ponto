import base64
import hashlib
import hmac

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.clock import now_utc
from app.core.config import get_settings
from app.core.errors import AppError, not_found
from app.core.security import new_opaque_token, sha256_hex
from app.models import Device
from app.services import audit


def _snapshot(d: Device) -> dict[str, object]:
    return {"name": d.name, "is_active": d.is_active, "require_location": d.require_location}


def list_devices(db: Session) -> list[Device]:
    return list(db.scalars(select(Device).order_by(Device.name, Device.id)).all())


def get(db: Session, device_id: int) -> Device:
    device = db.get(Device, device_id)
    if device is None:
        raise not_found("Dispositivo não encontrado.")
    return device


def create(
    db: Session, name: str, actor: audit.Actor, require_location: bool = False
) -> tuple[Device, str]:
    """Cadastra o terminal. O token devolvido é exibido uma única vez."""
    token = new_opaque_token()
    device = Device(name=name, token_hash=sha256_hex(token), require_location=require_location)
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


def set_require_location(db: Session, device_id: int, required: bool, actor: audit.Actor) -> Device:
    device = get(db, device_id)
    if device.require_location != required:
        before = _snapshot(device)
        device.require_location = required
        audit.record(
            db,
            actor=actor,
            action="device.set_require_location",
            entity_type="device",
            entity_id=device.id,
            before=before,
            after=_snapshot(device),
        )
        db.commit()
    return device


def link_code(device: Device) -> str:
    """Código do link permanente: `<id>.<assinatura>`. Derivado do segredo do servidor, então não é
    guardado em lugar nenhum e o administrador pode ver o link de novo quando quiser."""
    key = get_settings().jwt_secret.encode()
    message = f"device-link:{device.id}:{device.link_version}".encode()
    mac = base64.urlsafe_b64encode(hmac.new(key, message, hashlib.sha256).digest()).decode()
    return f"{device.id}.{mac.rstrip('=')}"


def get_link(db: Session, device_id: int, actor: audit.Actor) -> str:
    device = get(db, device_id)
    audit.record(
        db, actor=actor, action="device.link_view", entity_type="device", entity_id=device.id
    )
    db.commit()
    return link_code(device)


def renew_link(db: Session, device_id: int, actor: audit.Actor) -> str:
    """Invalida o link atual (quem o tem deixa de entrar) e devolve o novo."""
    device = get(db, device_id)
    device.link_version += 1
    audit.record(
        db, actor=actor, action="device.link_renew", entity_type="device", entity_id=device.id
    )
    db.commit()
    return link_code(device)


def _by_link_code(db: Session, code: str) -> Device | None:
    prefix, _, _ = code.partition(".")
    if not prefix.isdigit():
        return None
    device = db.get(Device, int(prefix))
    if device is None or not hmac.compare_digest(link_code(device), code):
        return None
    return device


def activate_with_code(db: Session, code: str) -> Device:
    """Confere o código do link permanente (não consome nada): o terminal usa o próprio código."""
    device = _by_link_code(db, code)
    if device is None or not device.is_active:
        raise AppError(
            403,
            "ACTIVATION_LINK_INVALID",
            "Link inválido ou desativado. Peça o link atual ao administrador.",
        )
    return device


def authenticate(db: Session, token: str) -> Device | None:
    device = db.scalar(select(Device).where(Device.token_hash == sha256_hex(token)))
    if device is None and "." in token:
        device = _by_link_code(db, token)  # link permanente do terminal
    if device is None or not device.is_active:
        return None
    device.last_seen_at = now_utc()
    db.commit()
    return device
