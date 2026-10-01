/** Diferença, em minutos inteiros, entre o relógio do servidor e o deste aparelho. */
export function clockSkewMinutes(serverTime: string, deviceNowMs: number): number {
  return Math.round((Date.parse(serverTime) - deviceNowMs) / 60_000);
}

/** Acima disso o terminal mostra um aviso: o horário oficial da batida é o do servidor. */
export const MAX_CLOCK_SKEW_MINUTES = 2;

export function clockWarning(skewMinutes: number): string | null {
  if (Math.abs(skewMinutes) <= MAX_CLOCK_SKEW_MINUTES) return null;
  const direction = skewMinutes > 0 ? "adiantado" : "atrasado";
  return (
    `Atenção: o relógio do servidor está ${Math.abs(skewMinutes)} min ${direction} em relação a este computador. ` +
    "Avise o administrador (reiniciar o Docker Desktop ou o computador corrige)."
  );
}
