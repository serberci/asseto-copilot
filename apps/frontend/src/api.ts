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

function headers(token: string): HeadersInit {
  return { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };
}

async function read<T>(path: string, token: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, { ...init, headers: { ...headers(token), ...(init?.headers ?? {}) } });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Request failed (${response.status})`);
  }
  return response.json() as Promise<T>;
}

export function getLive(token: string): Promise<LiveView> {
  return read("/api/v1/live", token);
}

export function getAnalysis(token: string, lapId: string): Promise<Analysis> {
  return read(`/api/v1/laps/${lapId}/analysis`, token);
}

export function setReference(token: string, sessionId: string, lapId: string): Promise<Session> {
  return read(`/api/v1/sessions/${sessionId}/reference`, token, {
    method: "POST",
    body: JSON.stringify({ lap_id: lapId }),
  });
}

export function ask(token: string, sessionId: string, question: string): Promise<Answer> {
  return read("/api/v1/copilot/ask", token, {
    method: "POST",
    body: JSON.stringify({ session_id: sessionId, question }),
  });
}
