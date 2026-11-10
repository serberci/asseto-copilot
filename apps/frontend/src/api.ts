export type Telemetry = {
  speed_mps: number;
  rpm: number;
  gear: string;
  throttle: number;
  brake: number;
  steering: number;
  normalized_progress: number;
  lap_number: number;
  current_lap_time_ms: number | null;
  last_lap_time_ms: number | null;
  best_lap_time_ms: number | null;
  track_id: string;
  car_model: string;
  player_nick: string;
  session_status: string;
  session_type: string;
};

export type Session = {
  id: string;
  track_id: string;
  car_model: string;
  player_nick: string;
  session_type: string;
  reference_lap_id: string | null;
};

export type Lap = {
  id: string;
  lap_number: number;
  lap_time_ms: number | null;
  valid: boolean;
  invalid_reasons: string[];
  sample_count: number;
};

export type Coaching = {
  id: string;
  rule_id: string;
  spoken_text: string;
  recommendation_allowed: boolean;
  confidence: number;
  time_impact_s: number | null;
  delivered_at: string | null;
};

export type LiveView = {
  connected_agents: number;
  session: Session | null;
  telemetry: Telemetry | null;
  laps: Lap[];
  coaching: Coaching[];
};

export type Analysis = {
  lap_id: string;
  reference_lap_id: string | null;
  report: {
    time_loss_s: number | null;
    corners: { name: string; time_impact_s: number | null; comparability: { ok: boolean; reasons: string[] } }[];
    events: { rule_id: string; advice: string; recommendation_allowed: boolean; spoken_text: string }[];
  } | null;
};

export type Answer = {
  spoken_response: string;
  model: string;
  grounded: boolean;
  intent: string;
};

export type Identity = {
  role: "administrator" | "driver";
  driver_id: string | null;
  display_name: string;
};

export type DriverAccount = {
  id: string;
  display_name: string;
  created_at: string;
  revoked: boolean;
};

export type CreatedDriver = {
  id: string;
  display_name: string;
  role: string;
};

export type CatalogLap = {
  id: string;
  session_id: string;
  lap_number: number;
  lap_time_ms: number | null;
  valid: boolean;
  invalid_reasons: string[];
  started_at: string;
  track_id: string;
  car_model: string;
  game: string;
  driver_id: string | null;
  driver_name: string | null;
};

export type PerformancePoint = {
  lap_id: string;
  lap_time_s: number;
  improvement_s: number | null;
  started_at: string;
};

export type ComparisonTip = {
  spoken_text: string;
  recommendation_allowed: boolean;
};

export type Benchmark = {
  personal: {
    available: boolean;
    time_loss_s: number | null;
    tips: ComparisonTip[];
  };
  others: {
    available: boolean;
    reason: string | null;
    driver_name: string | null;
    time_loss_s: number | null;
    tips: ComparisonTip[];
    board: { driver_name: string; lap_time_s: number }[];
  };
  pro: {
    available: boolean;
    reason?: string;
    spoken_text: string;
    tips: ComparisonTip[];
  };
  grip: { spoken_text: string }[];
};

async function read<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    credentials: "include",
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const body = (await response.json()) as { detail?: string };
      if (body.detail) message = body.detail;
    } catch {
      message = response.statusText || message;
    }
    throw new Error(message);
  }
  return response.json() as Promise<T>;
}

export function login(displayName: string, password: string): Promise<Identity> {
  return read("/api/v1/login", {
    method: "POST",
    body: JSON.stringify({ display_name: displayName, password }),
  });
}

export function logout(): Promise<{ ok: boolean }> {
  return read("/api/v1/logout", { method: "POST" });
}

export function getLive(): Promise<LiveView> {
  return read("/api/v1/live");
}

export function setReference(sessionId: string, lapId: string): Promise<Session> {
  return read(`/api/v1/sessions/${sessionId}/reference`, {
    method: "POST",
    body: JSON.stringify({ lap_id: lapId }),
  });
}

export function ask(sessionId: string, question: string): Promise<Answer> {
  return read("/api/v1/copilot/ask", {
    method: "POST",
    body: JSON.stringify({ session_id: sessionId, question }),
  });
}

export function getMe(): Promise<Identity> {
  return read("/api/v1/me");
}

export function getBenchmark(lapId: string): Promise<Benchmark> {
  return read(`/api/v1/laps/${lapId}/benchmark`);
}

export function listLaps(trackId?: string): Promise<{ laps: CatalogLap[] }> {
  const query = trackId ? `?track_id=${encodeURIComponent(trackId)}` : "";
  return read(`/api/v1/laps${query}`);
}

export function getPerformance(trackId: string): Promise<{ track_id: string; laps: PerformancePoint[] }> {
  return read(`/api/v1/performance?track_id=${encodeURIComponent(trackId)}`);
}

export function issueAgentToken(): Promise<{ token: string }> {
  return read("/api/v1/agent-token", { method: "POST" });
}

export function listDrivers(): Promise<{ drivers: DriverAccount[] }> {
  return read("/api/v1/drivers");
}

export function createDriver(displayName: string, password: string): Promise<CreatedDriver> {
  return read("/api/v1/drivers", {
    method: "POST",
    body: JSON.stringify({ display_name: displayName, password }),
  });
}

export function revokeDriver(driverId: string): Promise<{ revoked: boolean }> {
  return read(`/api/v1/drivers/${driverId}/revoke`, { method: "POST" });
}

export function claimUnassigned(driverId: string): Promise<{ sessions: number }> {
  return read(`/api/v1/drivers/${driverId}/claim-unassigned`, { method: "POST" });
}

export function deleteDriver(driverId: string): Promise<{ deleted: boolean }> {
  return read(`/api/v1/drivers/${driverId}`, { method: "DELETE" });
}

export function assignLap(lapId: string, driverId: string | null): Promise<{ id: string; driver_id: string | null }> {
  return read(`/api/v1/laps/${lapId}/assign`, {
    method: "POST",
    body: JSON.stringify({ driver_id: driverId }),
  });
}
