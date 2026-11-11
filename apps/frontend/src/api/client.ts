import type {
  Answer,
  Benchmark,
  CatalogLap,
  CreatedDriver,
  DriverAccount,
  Identity,
  LiveView,
  PerformancePoint,
  Session,
} from "./types";

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
