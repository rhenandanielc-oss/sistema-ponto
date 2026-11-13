/** Localização do celular, só para terminais com "exigir localização" (BUSINESS-RULES.md §4.7). */
import { ApiError } from "../api/client";

export interface Place {
  latitude: number;
  longitude: number;
  accuracy_m: number;
}

export function getPlace(): Promise<Place> {
  return new Promise((resolve, reject) => {
    if (!("geolocation" in navigator)) {
      reject(new ApiError(0, "LOCATION_UNAVAILABLE", "Este aparelho não informa a localização."));
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (p) => resolve({ latitude: p.coords.latitude, longitude: p.coords.longitude, accuracy_m: p.coords.accuracy }),
      (error) =>
        reject(
          new ApiError(
            0,
            "LOCATION_UNAVAILABLE",
            error.code === error.PERMISSION_DENIED
              ? "Permita a localização para este site (cadeado ao lado do endereço → Permissões → Localização)."
              : "Não foi possível obter a localização. Ative o GPS e tente de novo.",
          ),
        ),
      { enableHighAccuracy: true, timeout: 15_000, maximumAge: 10_000 },
    );
  });
}

export const LOCATION_BLOCKED =
  "A localização está bloqueada para este site. Toque no cadeado ao lado do endereço → Permissões → Localização → Permitir. (iPhone: Ajustes → Safari → Localização → Permitir.)";

/** Estado da permissão de localização, sem abrir nenhum pedido ("unknown" se o navegador não informa). */
export async function locationPermission(): Promise<"granted" | "denied" | "prompt" | "unknown"> {
  try {
    const status = await navigator.permissions.query({ name: "geolocation" });
    return status.state;
  } catch {
    return "unknown";
  }
}

