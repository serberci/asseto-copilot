export function kmh(speedMps: number | null | undefined): string {
  if (speedMps == null || Number.isNaN(speedMps)) return "—";
  return Math.round(speedMps * 3.6).toString();
}

export function lapTime(milliseconds: number | null | undefined): string {
  if (milliseconds == null || milliseconds < 0) return "—";
  const minutes = Math.floor(milliseconds / 60000);
  const seconds = Math.floor((milliseconds % 60000) / 1000);
  const millis = milliseconds % 1000;
  const secondsText = seconds.toString().padStart(2, "0");
  const millisText = millis.toString().padStart(3, "0");
  return minutes > 0 ? `${minutes}:${secondsText}.${millisText}` : `${seconds}.${millisText}`;
}

export function signedSeconds(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "—";
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(3)}`;
}

export function pedalWidth(value: number | null | undefined): string {
  const clamped = Math.min(1, Math.max(0, value ?? 0));
  return `${Math.round(clamped * 100)}%`;
}
