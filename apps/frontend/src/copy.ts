import { signedSeconds } from "./format";

type PersonalComparison = {
  available: boolean;
  time_loss_s: number | null;
};

type OtherComparison = {
  available: boolean;
  reason: string | null;
  driver_name: string | null;
  time_loss_s: number | null;
};

type SessionLabel = {
  track_id: string;
  car_model: string;
};

export function adviceLabel(recommendationAllowed: boolean): "ready" | "observation" {
  return recommendationAllowed ? "ready" : "observation";
}

export function coachingLabel(
  deliveredAt: string | null,
  recommendationAllowed: boolean,
): "spoken" | "ready" | "observation" {
  if (deliveredAt) return "spoken";
  return adviceLabel(recommendationAllowed);
}

export function lapState(valid: boolean, reasons: string[]): string {
  if (valid) return "valid";
  return reasons.join(", ") || "invalid";
}

export function dashboardStatus(connected: boolean, agents: number, session: SessionLabel | null): string {
  const link = connected ? "Dashboard connected" : "Dashboard offline";
  const agentLabel = agents === 1 ? "1 agent" : `${agents} agents`;
  const sessionLabel = session ? ` · ${session.track_id} · ${session.car_model}` : "";
  return `${link} · ${agentLabel}${sessionLabel}`;
}

export function changeLabel(improvement: number | null): string {
  if (improvement === null) return "First valid lap";
  if (improvement > 0) return `Faster by ${improvement.toFixed(3)} s`;
  if (improvement < 0) return `Slower by ${Math.abs(improvement).toFixed(3)} s`;
  return "Same time as the previous valid lap";
}

export function personalSummary(personal: PersonalComparison): string {
  if (!personal.available) return "No other lap of yours is available for this car and track.";
  if (personal.time_loss_s === null) return "Compared with your other lap.";
  return `Time versus your other lap: ${signedSeconds(personal.time_loss_s)} s.`;
}

export function otherSummary(others: OtherComparison): string {
  if (!others.available) {
    if (others.reason === "no_driver") return "These laps are not assigned to a driver.";
    return "No other driver has a valid lap in this car on this track.";
  }
  const name = others.driver_name ?? "another driver";
  if (others.time_loss_s === null) return `Compared with ${name}.`;
  return `Time versus ${name}: ${signedSeconds(others.time_loss_s)} s.`;
}

export function formatTimestamp(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
}
