import { FormEvent, useEffect, useState } from "react";
import {
  Answer,
  Benchmark,
  CatalogLap,
  Coaching,
  DriverAccount,
  Identity,
  Lap,
  LiveView,
  PerformancePoint,
  ask,
  assignLap,
  claimUnassigned,
  createDriver,
  deleteDriver,
  getBenchmark,
  getLive,
  getMe,
  getPerformance,
  issueAgentToken,
  listDrivers,
  listLaps,
  login,
  logout,
  revokeDriver,
  setReference,
} from "./api";
import { kmh, lapTime, pedalWidth, signedSeconds } from "./format";

type Tab = "account" | "session" | "laps" | "performance";

const TABS: { id: Tab; label: string }[] = [
  { id: "account", label: "Account" },
  { id: "session", label: "Current Session" },
  { id: "laps", label: "Laps" },
  { id: "performance", label: "Performance" },
];

export function App() {
  const [identity, setIdentity] = useState<Identity | null>(null);
  const [ready, setReady] = useState(false);
  const [tab, setTab] = useState<Tab>("session");

  useEffect(() => {
    getMe()
      .then(setIdentity)
      .catch(() => setIdentity(null))
      .finally(() => setReady(true));
  }, []);

  if (!ready) {
    return (
      <main>
        <p className="empty">Loading</p>
      </main>
    );
  }
  if (!identity) return <Login onSuccess={setIdentity} />;

  return (
    <main>
      <header>
        <div>
          <p className="eyebrow">Pit wall</p>
          <h1>Assetto Corsa Coach</h1>
        </div>
        <button
          type="button"
          onClick={() => {
            void logout().finally(() => {
              setTab("session");
              setIdentity(null);
            });
          }}
        >
          Log out
        </button>
      </header>
      <p className="empty">{identity.role === "administrator" ? "Administrator" : identity.display_name}</p>
      <nav className="tabs">
        {TABS.map((item) => (
          <button key={item.id} type="button" className={tab === item.id ? "on" : ""} onClick={() => setTab(item.id)}>
            {item.label}
          </button>
        ))}
      </nav>
      {tab === "account" ? <Account identity={identity} /> : null}
      {tab === "session" ? <CurrentSession /> : null}
      {tab === "laps" ? <Laps /> : null}
      {tab === "performance" ? <Performance /> : null}
    </main>
  );
}

function Login({ onSuccess }: { onSuccess: (who: Identity) => void }) {
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    try {
      onSuccess(await login(name.trim(), password));
      setError(null);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "The name or password is wrong");
    }
  }

  return (
    <main>
      <header>
        <div>
          <p className="eyebrow">Pit wall</p>
          <h1>Assetto Corsa Coach</h1>
        </div>
      </header>
      <form onSubmit={(event) => void submit(event)} className="login">
        <label>
          Name
          <input value={name} onChange={(event) => setName(event.target.value)} autoComplete="username" />
        </label>
        <label>
          Password
          <input
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            type="password"
            autoComplete="current-password"
          />
        </label>
        <button type="submit">Log in</button>
        {error ? <p className="error">{error}</p> : null}
      </form>
    </main>
  );
}

function Account({ identity }: { identity: Identity }) {
  const [token, setToken] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [drivers, setDrivers] = useState<DriverAccount[]>([]);
  const [laps, setLaps] = useState<CatalogLap[]>([]);
  const [choice, setChoice] = useState<Record<string, string>>({});
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");

  useEffect(() => {
    if (identity.role !== "administrator") return;
    Promise.all([listDrivers(), listLaps()])
      .then(([listed, catalog]) => {
        setDrivers(listed.drivers);
        setLaps(catalog.laps);
      })
      .catch((reason: Error) => setError(reason.message));
  }, [identity.role]);

  async function generate(event: FormEvent) {
    event.preventDefault();
    try {
      setToken((await issueAgentToken()).token);
      setError(null);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "The token was not created.");
    }
  }

  async function addDriver(event: FormEvent) {
    event.preventDefault();
    try {
      await createDriver(name.trim(), password);
      setName("");
      setPassword("");
      setDrivers((await listDrivers()).drivers);
      setError(null);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "The driver was not created.");
    }
  }

  return (
    <section>
      <h2>Account</h2>
      {identity.role === "driver" ? (
        <form onSubmit={(event) => void generate(event)} className="ask">
          <button type="submit">Generate agent token</button>
        </form>
      ) : (
        <p className="empty">Drivers generate their own agent token after they log in.</p>
      )}
      {token ? (
        <p className="answer">
          Copy this token into the Windows agent. It is shown once. If it is lost, generate another one and paste that into the agent.
          <span>{token}</span>
        </p>
      ) : null}
      {identity.role === "administrator" ? (
        <>
          <h2>Drivers</h2>
          <form onSubmit={(event) => void addDriver(event)} className="login">
            <label>
              Name
              <input value={name} onChange={(event) => setName(event.target.value)} maxLength={40} />
            </label>
            <label>
              Password
              <input value={password} onChange={(event) => setPassword(event.target.value)} type="password" />
            </label>
            <button type="submit">Create driver</button>
          </form>
          <p className="empty">Tell the driver this password. It is not shown again.</p>
          <ul className="drivers">
            {drivers.map((driver) => (
              <li key={driver.id}>
                <span>{driver.revoked ? "revoked" : "active"}</span>
                <p>
                  {driver.display_name}
                  {driver.revoked ? null : (
                    <>
                      {" "}
                      <button type="button" onClick={() => void claimUnassigned(driver.id).then(() => listDrivers().then((listed) => setDrivers(listed.drivers)))}>
                        Assign unassigned laps
                      </button>{" "}
                      <button type="button" onClick={() => void revokeDriver(driver.id).then(() => listDrivers().then((listed) => setDrivers(listed.drivers)))}>
                        Revoke login
                      </button>
                    </>
                  )}{" "}
                  <button
                    type="button"
                    onClick={() => {
                      if (!window.confirm(`Delete ${driver.display_name}? Their laps stay and become unassigned.`)) return;
                      void deleteDriver(driver.id)
                        .then(() => Promise.all([listDrivers(), listLaps()]))
                        .then(([listed, catalog]) => {
                          setDrivers(listed.drivers);
                          setLaps(catalog.laps);
                        })
                        .catch((reason: Error) => setError(reason.message));
                    }}
                  >
                    Delete
                  </button>
                </p>
              </li>
            ))}
          </ul>
          <h2>Laps</h2>
          <p className="empty">Choose a driver for one lap. Unassigned leaves the lap with nobody.</p>
          {laps.length === 0 ? <p className="empty">No laps yet.</p> : null}
          <table>
            <thead>
              <tr>
                <th>Track</th>
                <th>Car</th>
                <th>Lap</th>
                <th>Time</th>
                <th>Driver</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {laps.map((lap) => (
                <tr key={lap.id}>
                  <td>{lap.track_id}</td>
                  <td>{lap.car_model}</td>
                  <td>{lap.lap_number}</td>
                  <td>{lapTime(lap.lap_time_ms)}</td>
                  <td>
                    <select
                      value={choice[lap.id] ?? lap.driver_id ?? ""}
                      onChange={(event) => setChoice({ ...choice, [lap.id]: event.target.value })}
                    >
                      <option value="">Unassigned</option>
                      {drivers
                        .filter((driver) => !driver.revoked)
                        .map((driver) => (
                          <option key={driver.id} value={driver.id}>
                            {driver.display_name}
                          </option>
                        ))}
                    </select>
                  </td>
                  <td>
                    <button
                      type="button"
                      onClick={() => {
                        const selected = choice[lap.id] ?? lap.driver_id ?? "";
                        void assignLap(lap.id, selected || null)
                          .then(() => listLaps())
                          .then((catalog) => {
                            setLaps(catalog.laps);
                            setChoice((current) => {
                              const next = { ...current };
                              delete next[lap.id];
                              return next;
                            });
                          })
                          .catch((reason: Error) => setError(reason.message));
                      }}
                    >
                      Assign
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      ) : null}
      {error ? <p className="error">{error}</p> : null}
    </section>
  );
}

function CurrentSession() {
  const [live, setLive] = useState<LiveView | null>(null);
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [question, setQuestion] = useState("where am I losing time");
  const [answer, setAnswer] = useState<Answer | null>(null);
  const [asking, setAsking] = useState(false);
  const [analysisLoss, setAnalysisLoss] = useState<number | null>(null);

  useEffect(() => {
    let closed = false;
    let socket: WebSocket | null = null;
    getLive()
      .then((view) => {
        if (!closed) setLive(view);
      })
      .catch((reason: Error) => setError(reason.message));
    const protocol = window.location.protocol === "https:" ? "wss" : "ws";
    socket = new WebSocket(`${protocol}://${window.location.host}/ws/dashboard`);
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
  }, []);

  const latestValidId = live?.laps.filter((lap) => lap.valid).at(-1)?.id;
  useEffect(() => {
    if (!latestValidId) {
      setAnalysisLoss(null);
      return;
    }
    getBenchmark(latestValidId)
      .then((report) => setAnalysisLoss(report.personal.time_loss_s))
      .catch(() => setAnalysisLoss(null));
  }, [latestValidId]);

  async function chooseReference(lap: Lap) {
    if (!live?.session) return;
    await setReference(live.session.id, lap.id);
    setLive(await getLive());
  }

  async function submitQuestion(event: FormEvent) {
    event.preventDefault();
    if (!live?.session) return;
    setAsking(true);
    try {
      setAnswer(await ask(live.session.id, question));
      setError(null);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "The question failed.");
    } finally {
      setAsking(false);
    }
  }

  const telemetry = live?.telemetry;

  return (
    <section>
      <p className={connected ? "status on" : "status"}>
        {connected ? "Dashboard connected" : "Dashboard offline"} ·{" "}
        {(live?.connected_agents ?? 0) === 1 ? "1 agent" : `${live?.connected_agents ?? 0} agents`}
        {live?.session ? ` · ${live.session.track_id} · ${live.session.car_model}` : ""}
      </p>
      {error ? <p className="error">{error}</p> : null}
      {!live?.session ? <p className="empty">No session yet. Start the Windows agent with this driver's token.</p> : null}
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
          <strong>{signedSeconds(analysisLoss)}</strong>
          <em>vs your reference</em>
        </div>
      </section>
      <section className="pedals">
        <Bar label="Throttle" value={telemetry?.throttle} kind="throttle" />
        <Bar label="Brake" value={telemetry?.brake} kind="brake" />
        <p>
          Steering {telemetry ? telemetry.steering.toFixed(3) : "—"} · progress{" "}
          {telemetry ? `${Math.round(telemetry.normalized_progress * 100)}%` : "—"}
        </p>
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
    </section>
  );
}

function Laps() {
  const [laps, setLaps] = useState<CatalogLap[]>([]);
  const [track, setTrack] = useState("");
  const [selected, setSelected] = useState<CatalogLap | null>(null);
  const [benchmark, setBenchmark] = useState<Benchmark | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listLaps()
      .then((body) => setLaps(body.laps))
      .catch((reason: Error) => setError(reason.message));
  }, []);

  useEffect(() => {
    if (!selected) return;
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") setSelected(null);
    }
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    window.addEventListener("keydown", onKey);
    return () => {
      document.body.style.overflow = previous;
      window.removeEventListener("keydown", onKey);
    };
  }, [selected]);

  const tracks = [...new Set(laps.map((lap) => lap.track_id))];
  const shown = track ? laps.filter((lap) => lap.track_id === track) : laps;

  async function openLap(lap: CatalogLap) {
    setSelected(lap);
    setBenchmark(null);
    setDetailError(null);
    try {
      setBenchmark(await getBenchmark(lap.id));
    } catch (reason) {
      setDetailError(reason instanceof Error ? reason.message : "The lap was not found.");
    }
  }

  return (
    <section>
      <h2>Laps</h2>
      <label>
        Track
        <select value={track} onChange={(event) => setTrack(event.target.value)}>
          <option value="">All tracks</option>
          {tracks.map((item) => (
            <option key={item} value={item}>
              {item}
            </option>
          ))}
        </select>
      </label>
      {error ? <p className="error">{error}</p> : null}
      <table>
        <thead>
          <tr>
            <th>Track</th>
            <th>Car</th>
            <th>Lap</th>
            <th>Time</th>
            <th>State</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {shown.map((lap) => (
            <tr key={lap.id}>
              <td>{lap.track_id}</td>
              <td>{lap.car_model}</td>
              <td>{lap.lap_number}</td>
              <td>{lapTime(lap.lap_time_ms)}</td>
              <td>{lap.valid ? "valid" : lap.invalid_reasons.join(", ") || "invalid"}</td>
              <td>
                <button type="button" onClick={() => void openLap(lap)}>
                  Details
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {shown.length === 0 ? <p className="empty">No laps for this track.</p> : null}
      {selected ? (
        <div className="drawer-backdrop" onClick={() => setSelected(null)}>
          <aside
            className="drawer"
            role="dialog"
            aria-modal="true"
            aria-label={`Lap ${selected.lap_number} on ${selected.track_id}`}
            onClick={(event) => event.stopPropagation()}
          >
            <header>
              <div>
                <p className="eyebrow">{selected.track_id}</p>
                <h2>
                  Lap {selected.lap_number} · {lapTime(selected.lap_time_ms)}
                </h2>
              </div>
              <button type="button" onClick={() => setSelected(null)}>
                Close
              </button>
            </header>
            <dl className="facts">
              <dt>Car</dt>
              <dd>{selected.car_model}</dd>
              <dt>Game</dt>
              <dd>{selected.game}</dd>
              <dt>Driver</dt>
              <dd>{selected.driver_name ?? "Unassigned"}</dd>
              <dt>Started</dt>
              <dd>{when(selected.started_at)}</dd>
              <dt>State</dt>
              <dd>{selected.valid ? "Valid" : selected.invalid_reasons.join(", ") || "Invalid"}</dd>
            </dl>
            {detailError ? <p className="error">{detailError}</p> : null}
            {benchmark ? <LapReport benchmark={benchmark} /> : detailError ? null : <p className="empty">Loading this lap.</p>}
          </aside>
        </div>
      ) : null}
    </section>
  );
}

function Performance() {
  const [tracks, setTracks] = useState<string[]>([]);
  const [track, setTrack] = useState("");
  const [points, setPoints] = useState<PerformancePoint[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listLaps()
      .then((body) => {
        const names = [...new Set(body.laps.map((lap) => lap.track_id))];
        setTracks(names);
        setTrack((current) => current || names[0] || "");
      })
      .catch((reason: Error) => setError(reason.message));
  }, []);

  useEffect(() => {
    if (!track) return;
    getPerformance(track)
      .then((body) => setPoints(body.laps))
      .catch((reason: Error) => setError(reason.message));
  }, [track]);

  return (
    <section>
      <h2>Performance</h2>
      <label>
        Track
        <select value={track} onChange={(event) => setTrack(event.target.value)}>
          {tracks.map((item) => (
            <option key={item} value={item}>
              {item}
            </option>
          ))}
        </select>
      </label>
      {error ? <p className="error">{error}</p> : null}
      {points.length === 0 ? <p className="empty">No valid laps on this track.</p> : null}
      <table>
        <thead>
          <tr>
            <th>Time</th>
            <th>Change</th>
          </tr>
        </thead>
        <tbody>
          {points.map((point) => (
            <tr key={point.lap_id}>
              <td>{point.lap_time_s.toFixed(3)} s</td>
              <td>{changeLabel(point.improvement_s)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

function changeLabel(improvement: number | null): string {
  if (improvement === null) return "First valid lap";
  if (improvement > 0) return `Faster by ${improvement.toFixed(3)} s`;
  if (improvement < 0) return `Slower by ${Math.abs(improvement).toFixed(3)} s`;
  return "Same time as the previous valid lap";
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

function LapReport({ benchmark }: { benchmark: Benchmark }) {
  return (
    <>
      <h2>Your laps</h2>
      <p>{personalSummary(benchmark)}</p>
      <TipList tips={benchmark.personal.tips} />
      <h2>Other drivers</h2>
      <p>{otherSummary(benchmark)}</p>
      <TipList tips={benchmark.others.tips} />
      {benchmark.others.board.length ? (
        <ul className="board">
          {benchmark.others.board.map((row) => (
            <li key={`${row.driver_name}-${row.lap_time_s}`}>
              <span>{row.driver_name}</span>
              <p>{row.lap_time_s.toFixed(3)} s</p>
            </li>
          ))}
        </ul>
      ) : null}
      <h2>Pro file</h2>
      {benchmark.pro.available ? null : <p>{benchmark.pro.spoken_text}</p>}
      <TipList tips={benchmark.pro.tips} />
      <h2>Grip</h2>
      {benchmark.grip.length ? (
        benchmark.grip.map((flag) => <p key={flag.spoken_text}>{flag.spoken_text}</p>)
      ) : (
        <p className="empty">No wheel slip or tyres off the track were recorded.</p>
      )}
    </>
  );
}

function TipList({ tips }: { tips: Benchmark["personal"]["tips"] }) {
  if (!tips.length) return null;
  return (
    <div className="tips">
      {tips.map((tip) => (
        <p key={tip.spoken_text}>
          <span className={tip.recommendation_allowed ? "ready" : "observation"}>
            {tip.recommendation_allowed ? "ready" : "observation"}
          </span>{" "}
          {tip.spoken_text}
        </p>
      ))}
    </div>
  );
}

function personalSummary(benchmark: Benchmark): string {
  if (!benchmark.personal.available) return "No other lap of yours is available for this car and track.";
  if (benchmark.personal.time_loss_s === null) return "Compared with your other lap.";
  return `Time versus your other lap: ${signedSeconds(benchmark.personal.time_loss_s)} s.`;
}

function otherSummary(benchmark: Benchmark): string {
  if (!benchmark.others.available) {
    if (benchmark.others.reason === "no_driver") return "These laps are not assigned to a driver.";
    return "No other driver has a valid lap in this car on this track.";
  }
  const name = benchmark.others.driver_name ?? "another driver";
  if (benchmark.others.time_loss_s === null) return `Compared with ${name}.`;
  return `Time versus ${name}: ${signedSeconds(benchmark.others.time_loss_s)} s.`;
}

function when(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
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
