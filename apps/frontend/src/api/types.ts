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
