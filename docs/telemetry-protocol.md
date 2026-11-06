# Telemetry protocol 1.0.0

Every message is a JSON object:

| Field | Meaning |
|---|---|
| `schema_version` | `1.0.0` only, until a later version is added on purpose |
| `game` | `assetto_corsa` |
| `agent_id` | Stable id from the agent settings |
| `session_id` | Null until the host has opened a session; then the host's id |
| `sequence` | Increases by one for each message from this agent process. A hello on reconnect uses the next number. It does not restart at zero. |
| `timestamp` | Timezone-aware UTC time of the message |
| `type` | `hello`, `telemetry`, `heartbeat`, or `goodbye` |
| `payload` | The object for that type |

Unknown fields are rejected. A naive timestamp is rejected. The host replies on the telemetry socket with `{"type":"ack","sequence":...,"session_id":...}` or `{"type":"error","detail":...}`. A bad token closes the socket with code 1008. The token is `Authorization: Bearer <token>` for the agent, or `?token=` for the dashboard because a browser socket cannot set that header.

A telemetry sample is published when the physics page or the graphics page has a new `packetId`. A repeated packet id is stale and is not sent as a fresh sample. Both flags are still on the sample when one side moved and the other did not.

## Units

| Field | Unit | Status |
|---|---|---|
| `speed_mps` | meters per second, from `speedKmh / 3.6` | The source field is named km/h. The dashboard multiplies by 3.6 for display. |
| `throttle`, `brake`, `clutch` | 0 to 1 | Values slightly outside that range are clamped. Values outside −0.05 to 1.05 are rejected. |
| `rpm`, `gear_raw` | game values | Gear 0 is reverse, 1 is neutral, 2 is first. |
| `normalized_progress` | 0 to 1 along the track spline | From `normalizedCarPosition`. |
| `distance_traveled_m` | meters | |
| `current_lap_time_ms`, `last_lap_time_ms`, `best_lap_time_ms` | milliseconds | Negative game values become null. Zero is kept. |
| `velocity_mps` | meters per second, Assetto Corsa world axes | |
| `acceleration_g` | g | |
| `heading_rad`, `pitch_rad`, `roll_rad`, `camber_rad`, `angular_speed_rad_s` | radians or radians per second | Field names in the game page say so for camber and wheel angular speed. |
| `core_temp_c` and the other `*_temp_c` fields | degrees Celsius | Confirm the tyre readout on the first live session. |
| `fuel_l` | liters | Confirm against the in-game fuel number. |
| `steering` | raw `steerAngle` | Expected to be radians. The first live session must confirm the magnitude before any coaching uses it. |
| `wheels[].pressure` | raw `wheelsPressure` | Expected psi. |
| `wheels[].load` | raw `wheelLoad` | Expected newtons. |
| `wheels[].slip`, `wear`, `dirt` | raw game values | Not rescaled. |

Wheel order is FL, FR, RL, RR.

## Session and lap

A session opens on the first telemetry sample and stays open while the agent, track, track configuration, car, and session type stay the same. A change starts another session.

`lap_number` is `completed_laps + 1`. The lap closes when `completed_laps` increases. That sample belongs to the next lap. The closed lap's time is `last_lap_time_ms` on the sample that crossed the line.

A lap is invalid when it has fewer than 20 samples, does not span progress from at most 0.05 to at least 0.95, is mostly in the pit, has a gap of more than one second, or the progress jumps backward by more than 0.2. Only samples whose session status is `live` are added to a lap. Every accepted telemetry message is still appended to the session JSONL.

Samples for a finished lap are written to Parquet. The full payload is in `payload_json`, so later analysis can be recomputed. A JSONL copy of every accepted telemetry message is kept under `data/sessions/<id>/telemetry.jsonl`.

## Lap delta

For two valid laps of the same car and track, time at a progress point is interpolated. Delta is current elapsed time minus reference elapsed time. Positive means the current lap is slower. The reference is the fastest other valid lap, unless the dashboard has selected one.

Corner entry, apex, and exit come only from a track file with `calibrated: true` and a matching `track_id`. A corner whose progress wraps the start line is not supported. The bundled `synthetic-oval` file is a test track.

Coaching may describe a brake point. It may recommend treating the reference as the comparison only when the laps are the same car and track and the entry speeds are within 3%. Otherwise the event is an observation: `recommendation_allowed` is false, and the scheduler will not speak it. Spoken advice also waits until brake is below 0.15, throttle is at least 0.5, and the car is outside a calibrated corner. The same dedup key is not spoken again for 20 seconds.

## HTTP

All `/api/v1` routes except `GET /api/v1/health` require the bearer token.

| Method | Path | Body / result |
|---|---|---|
| GET | `/api/v1/health` | `{status, version}` |
| GET | `/api/v1/live` | Current session, telemetry, laps, coaching |
| GET | `/api/v1/sessions` | Session list |
| GET | `/api/v1/sessions/{id}` | One session |
| GET | `/api/v1/sessions/{id}/laps` | Lap rows |
| GET | `/api/v1/sessions/{id}/coaching` | Coaching rows |
| POST | `/api/v1/sessions/{id}/reference` | `{"lap_id"}` |
| GET | `/api/v1/laps/{id}/analysis` | Recomputed delta, corners, events |
| GET | `/api/v1/tracks` | Bundled and user track files. Names starting with `_` are templates and are omitted. `calibrated: false` is listed and is not used for coaching. |
| POST | `/api/v1/copilot/ask` | `{"question", "session_id"}` |
| POST | `/api/v1/replay` | `{"jsonl"}` of protocol messages |
| WS | `/ws/telemetry` | Agent stream |
| WS | `/ws/dashboard?token=` | Snapshot on connect, then on each accepted agent message |
| WS | `/ws/audio` | JSON `{"pcm_hex", "sample_rate", "session_id"}` |

`fixtures/synthetic-session.jsonl` is a protocol recording of two synthetic laps. `fixtures/page-sample.json` is a shared-memory page image for `coach-agent --fixture`, not a protocol recording.
