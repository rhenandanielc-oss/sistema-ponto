"""Trava por localização dos terminais pessoais (BUSINESS-RULES.md §4.7).

A posição vem do celular e pode ser falsificada por quem entende de GPS: a trava impede o ponto
"sem querer" de casa ou da rua, não uma fraude deliberada.
"""

from math import asin, cos, radians, sin, sqrt

from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models import Device
from app.services import settings_service

MAX_ACCURACY_METERS = 150.0  # acima disso o GPS não permite saber se a pessoa está no local
EARTH_RADIUS_METERS = 6_371_000.0


def distance_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distância entre dois pontos (fórmula de haversine)."""
    p1, p2 = radians(lat1), radians(lat2)
    dp, dl = p2 - p1, radians(lon2 - lon1)
    a = sin(dp / 2) ** 2 + cos(p1) * cos(p2) * sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_METERS * asin(sqrt(a))


def check(
    db: Session,
    device: Device,
    latitude: float | None,
    longitude: float | None,
    accuracy_m: float | None,
) -> None:
    """Recusa a operação se o terminal exige localização e o celular não está no restaurante."""
    if not device.require_location:
        return
    settings = settings_service.load(db)
    if settings.location_latitude is None or settings.location_longitude is None:
        raise AppError(
            409,
            "LOCATION_NOT_CONFIGURED",
            "O local do restaurante não foi cadastrado. Avise o administrador.",
        )
    if latitude is None or longitude is None:
        raise AppError(
            422,
            "LOCATION_REQUIRED",
            "Ative a localização do celular e permita o acesso neste site.",
        )
    if accuracy_m is None or accuracy_m > MAX_ACCURACY_METERS:
        raise AppError(
            422,
            "LOCATION_IMPRECISE",
            "Sinal de localização fraco. Ative o GPS, vá para perto de uma janela e tente de novo.",
        )
    distance = distance_meters(
        latitude, longitude, settings.location_latitude, settings.location_longitude
    )
    if distance > settings.location_radius_meters:
        raise AppError(
            403,
            "LOCATION_OUT_OF_RANGE",
            "Você precisa estar no restaurante para bater o ponto.",
            {"distance_meters": round(distance)},
        )
