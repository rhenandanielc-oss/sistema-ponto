"""Trava por localização dos terminais pessoais (BUSINESS-RULES.md §4.7).

A posição vem do celular e pode ser falsificada por quem entende de GPS: a trava impede o ponto
"sem querer" de casa ou da rua, não uma fraude deliberada.
"""

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from math import asin, cos, radians, sin, sqrt
from typing import Any

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


# --- Achar o local do restaurante sem digitar latitude e longitude -----------------------------

# --- Achar o local do restaurante sem digitar latitude e longitude -----------------------------


@dataclass(frozen=True)
class Located:
    latitude: float
    longitude: float
    label: str


_NUM = r"(-?\d{1,3}(?:\.\d+)?)"
_PAIR = re.compile(rf"^\s*{_NUM}\s*[,;\s]\s*{_NUM}\s*$")
_GOOGLE_PIN = re.compile(r"!3d(-?\d+\.\d+)!4d(-?\d+\.\d+)")  # o alfinete do lugar
_GOOGLE_AT = re.compile(r"@(-?\d+\.\d+),(-?\d+\.\d+)")  # centro da tela do mapa
_GOOGLE_Q = re.compile(r"[?&](?:q|ll|query|destination)=(-?\d+\.\d+)(?:,|%2C)(-?\d+\.\d+)")
GOOGLE_HOSTS = {
    "maps.app.goo.gl",
    "goo.gl",
    "maps.google.com",
    "google.com",
    "www.google.com",
    "google.com.br",
    "www.google.com.br",
}
NOMINATIM = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "Mozilla/5.0 (sistema-ponto)"


def _valid(lat: float, lng: float) -> tuple[float, float] | None:
    return (lat, lng) if -90 <= lat <= 90 and -180 <= lng <= 180 else None


def coords_from_pair(text: str) -> tuple[float, float] | None:
    """Aceita "-22.95, -46.54" (como o Google Maps copia) ou separado por espaço."""
    match = _PAIR.match(text)
    return _valid(float(match.group(1)), float(match.group(2))) if match else None


def coords_from_google_url(url: str) -> tuple[float, float] | None:
    decoded = urllib.parse.unquote(url)
    for pattern in (_GOOGLE_PIN, _GOOGLE_AT, _GOOGLE_Q):
        match = pattern.search(decoded)
        if match:
            return _valid(float(match.group(1)), float(match.group(2)))
    return None


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args: Any, **kwargs: Any) -> None:
        return None


def _next_hop(url: str) -> str | None:
    """Pede a página e devolve o endereço para onde ela redireciona (None se não redireciona)."""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        urllib.request.build_opener(_NoRedirect).open(request, timeout=10).close()
    except urllib.error.HTTPError as exc:
        location = exc.headers.get("Location")
        if exc.code in (301, 302, 303, 307, 308) and location:
            return urllib.parse.urljoin(url, location)
    return None


def _follow_google_link(url: str) -> tuple[float, float] | None:
    """Segue link curto do Maps (só entre hosts do Google) até achar as coordenadas."""
    for _ in range(5):
        host = (urllib.parse.urlparse(url).hostname or "").lower()
        if host not in GOOGLE_HOSTS:
            return None
        coords = coords_from_google_url(url)
        if coords:
            return coords
        nxt = _next_hop(url)
        if nxt is None:
            return None
        url = nxt
    return None


def _fetch_json(url: str) -> Any:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.loads(response.read())


def _geocode(query: str) -> Located | None:
    params = urllib.parse.urlencode(
        {"q": query, "format": "jsonv2", "limit": 1, "countrycodes": "br"}
    )
    results = _fetch_json(f"{NOMINATIM}?{params}")
    if not results:
        return None
    first = results[0]
    return Located(float(first["lat"]), float(first["lon"]), str(first.get("display_name", query)))


def locate(query: str) -> Located:
    """Descobre o local por coordenadas coladas, link do Google Maps ou endereço."""
    text = query.strip()
    try:
        pair = coords_from_pair(text)
        if pair:
            return Located(pair[0], pair[1], "Coordenadas informadas")
        if re.match(r"^https?://", text, re.IGNORECASE):
            coords = _follow_google_link(text)
            if coords:
                return Located(coords[0], coords[1], "Link do Google Maps")
            raise AppError(
                422,
                "LOCATION_NOT_FOUND",
                "Não achei o local nesse link. Use o link de compartilhar do Maps ou o endereço.",
            )
        found = _geocode(text)
    except (urllib.error.URLError, TimeoutError, ValueError, KeyError) as exc:
        raise AppError(
            502,
            "LOCATION_LOOKUP_FAILED",
            "Não consegui consultar o mapa agora. Tente de novo ou cole as coordenadas.",
        ) from exc
    if found is None:
        raise AppError(
            422,
            "LOCATION_NOT_FOUND",
            "Endereço não encontrado. Confira a rua e a cidade, ou use o link do Google Maps.",
        )
    return found
