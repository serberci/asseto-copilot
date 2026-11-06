import { FormEvent, useEffect, useState } from "react";
import { Analysis, Answer, Coaching, Lap, LiveView, ask, getAnalysis, getLive, setReference } from "./api";
import { kmh, lapTime, pedalWidth, signedSeconds } from "./format";

const TOKEN_KEY = "coach-token";

export function App() {
  const [token, setToken] = useState(() => localStorage.getItem(TOKEN_KEY) ?? "");
  const [draft, setDraft] = useState(token);
  const [live, setLive] = useState<LiveView | null>(null);
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [connected, setConnected] = useState(false);
  const [question, setQuestion] = useState("where am I losing time");
  const [answer, setAnswer] = useState<Answer | null>(null);
  const [asking, setAsking] = useState(false);

  useEffect(() => {
    if (!token) return;
    let socket: WebSocket | null = null;
    let closed = false;
    getLive(token)
      .then((view) => {
        if (!closed) {
          setLive(view);
          setError(null);
        }
      })
      .catch((reason: Error) => setError(reason.message));
    const protocol = window.location.protocol === "https:" ? "wss" : "ws";
    socket = new WebSocket(`${protocol}://${window.location.host}/ws/dashboard?token=${encodeURIComponent(token)}`);
    socket.onopen = () => setConnected(true);
    socket.onclose = () => setConnected(false);
    socket.onmessage = (event) => {
      const payload = JSON.parse(event.data) as { type: string } & LiveView;
      if (payload.type === "snapshot") setLive(payload);
    };
    return () => {
      closed = true;
      socket?.close();
    };
  }, [token]);

  const latestValidId = live?.laps.filter((lap) => lap.valid).at(-1)?.id;
  useEffect(() => {
    if (!token || !latestValidId) {
      setAnalysis(null);
      return;
    }
    getAnalysis(token, latestValidId)
      .then(setAnalysis)
      .catch(() => setAnalysis(null));
  }, [token, latestValidId]);

  function saveToken(event: FormEvent) {
    event.preventDefault();
    const next = draft.trim();
    localStorage.setItem(TOKEN_KEY, next);
    setToken(next);
    setAnswer(null);
  }

  async function chooseReference(lap: Lap) {
    if (!token || !live?.session) return;
    await setReference(token, live.session.id, lap.id);
    const view = await getLive(token);
    setLive(view);
    const latest = [...view.laps].reverse().find((item) => item.valid);
    if (latest) setAnalysis(await getAnalysis(token, latest.id));
  }

  async function submitQuestion(event: FormEvent) {
    event.preventDefault();
    if (!token || !live?.session) return;
    setAsking(true);
    try {
      setAnswer(await ask(token, live.session.id, question));
      setError(null);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "The question failed.");
    } finally {
      setAsking(false);
    }
  }

  const telemetry = live?.telemetry;
  const loss = analysis?.report?.time_loss_s;

  return (
    <main>
      <header>
        <div>
          <p className="eyebrow">Pit wall</p>
          <h1>Assetto Corsa Coach</h1>
        </div>
        <form onSubmit={saveToken} className="token">
          <label>
            Token
            <input value={draft} onChange={(event) => setDraft(event.target.value)} type="password" autoComplete="off" />
          </label>
          <button type="submit">Connect</button>
        </form>
      </header>

      <p className={connected ? "status on" : "status"}>
        {connected ? "Dashboard connected" : "Dashboard offline"} ·{" "}
        {(live?.connected_agents ?? 0) === 1 ? "1 agent" : `${live?.connected_agents ?? 0} agents`}
        {live?.session ? ` · ${live.session.track_id} · ${live.session.car_model}` : ""}
      </p>
      {error ? <p className="error">{error}</p> : null}

      {!token ? <p className="empty">Paste the token from the AI host data directory to open the session.</p> : null}
      {token && !live?.session ? (
        <p className="empty">No session yet. Start the Windows agent, or replay the synthetic session from INSTALL.</p>
      ) : null}

      <section className="readout">
        <div>
          <span>Speed</span>
          <strong>{kmh(telemetry?.speed_mps)}</strong>
          <em>km/h</em>
        </div>
        <div>
          <span>Gear</span>
          <strong>{telemetry?.gear ?? "—"}</strong>
          <em>{telemetry?.session_status ?? "waiting"}</em>
        </div>
        <div>
          <span>RPM</span>
          <strong>{telemetry ? telemetry.rpm : "—"}</strong>
          <em>lap {telemetry?.lap_number ?? "—"}</em>
        </div>
        <div>
          <span>Delta</span>
          <strong>{signedSeconds(loss)}</strong>
          <em>vs reference</em>
        </div>
      </section>

      <section className="pedals">
        <Bar label="Throttle" value={telemetry?.throttle} kind="throttle" />
        <Bar label="Brake" value={telemetry?.brake} kind="brake" />
        <p>Steering {telemetry ? telemetry.steering.toFixed(3) : "—"} · progress {telemetry ? `${Math.round(telemetry.normalized_progress * 100)}%` : "—"}</p>
      </section>

      <section className="split">
        <article>
          <h2>Laps</h2>
          <table>
            <thead>
              <tr>
                <th>Lap</th>
                <th>Time</th>
                <th>State</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {(live?.laps ?? []).map((lap) => (
                <tr key={lap.id}>
                  <td>{lap.lap_number}</td>
                  <td>{lapTime(lap.lap_time_ms)}</td>
                  <td>{lap.valid ? "valid" : lap.invalid_reasons.join(", ") || "invalid"}</td>
                  <td>
                    {lap.valid ? (
                      <button type="button" onClick={() => void chooseReference(lap)}>
                        {live?.session?.reference_lap_id === lap.id ? "Reference" : "Use as reference"}
                      </button>
                    ) : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="times">
            Current {lapTime(telemetry?.current_lap_time_ms)} · last {lapTime(telemetry?.last_lap_time_ms)} · best{" "}
            {lapTime(telemetry?.best_lap_time_ms)}
          </p>
        </article>
        <article>
          <h2>Coaching</h2>
          <ul>
            {(live?.coaching ?? []).map((event) => (
              <li key={event.id}>
                <CoachingLine event={event} />
              </li>
            ))}
          </ul>
          {(live?.coaching ?? []).length === 0 ? <p className="empty">No coaching events for this session.</p> : null}
        </article>
      </section>

      <section>
        <h2>Ask</h2>
        <form onSubmit={(event) => void submitQuestion(event)} className="ask">
          <input value={question} onChange={(event) => setQuestion(event.target.value)} disabled={!live?.session} />
          <button type="submit" disabled={!live?.session || asking}>
            {asking ? "Asking" : "Ask"}
          </button>
        </form>
        {answer ? (
          <p className="answer">
            {answer.spoken_response}
            <span>{answer.model}</span>
          </p>
        ) : null}
      </section>
    </main>
  );
}

function Bar({ label, value, kind }: { label: string; value: number | undefined; kind: "throttle" | "brake" }) {
  return (
    <div className="bar">
      <span>{label}</span>
      <div>
        <i className={kind} style={{ width: pedalWidth(value) }} />
      </div>
    </div>
  );
}

function CoachingLine({ event }: { event: Coaching }) {
  const label = event.delivered_at ? "spoken" : event.recommendation_allowed ? "ready" : "observation";
  return (
    <>
      <span className={label}>{label}</span>
      <p>{event.spoken_text}</p>
    </>
  );
}
