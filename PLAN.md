# Assetto Corsa Coach — Implementation Plan

## Project goal

Build a local-first, voice-enabled driving coach for the **original Assetto Corsa**. It reads live telemetry from the gaming PC, analyses driving technique and lap performance on a separate AI host, and provides both proactive spoken coaching and answers to voice questions.

The initial setup uses two computers:

1. **Gaming PC (Windows):** runs Assetto Corsa and a lightweight background agent that reads shared memory and publishes normalized telemetry.
2. **AI host (MacBook, Apple Silicon, 24 GB unified memory):** receives telemetry, records sessions, analyses laps, runs local AI/STT/TTS components, and hosts the dashboard.

The design must allow the AI host to move from the MacBook to a VPS/cloud host later without requiring changes to the game-specific telemetry collector beyond connection configuration.

## Product principles

- Keep telemetry acquisition and numerical analysis deterministic; do not ask an LLM to interpret every telemetry sample.
- Keep the telemetry path independent from the conversational/voice path.
- Make the game-specific acquisition adapter replaceable. The first adapter targets original Assetto Corsa; ACC is out of scope for the MVP.
- Prefer local processing and storage initially.
- Keep spoken coaching short, actionable, evidence-based, and non-repetitive.
- Do not make unsafe driving recommendations from insufficient or incomparable data.
- Version the telemetry protocol and validate messages at system boundaries.

## Target architecture

### Gaming PC — Windows

**Assetto Corsa Coach Agent — standalone Windows desktop application**

The gaming-PC component should be delivered as an installable Windows application, not as a script the user has to launch manually.

- Build the telemetry core in Python and keep it independent from the desktop UI.
- Provide a PySide6 (Qt) desktop interface with a Windows system-tray mode.
- Detect whether original Assetto Corsa is running and whether shared memory is available.
- Read the `acpmf_physics`, `acpmf_graphics`, and `acpmf_static` mappings using the official/verified structure layouts.
- Normalize game-specific structures into versioned application telemetry models.
- Maintain a short in-memory ring buffer and optionally record raw/debug data locally.
- Publish telemetry to the configured backend over a persistent WebSocket connection.
- Reconnect automatically after network interruptions.
- Show game, telemetry, backend connection, and audio-device status in the UI and tray menu.
- Provide a settings screen for the backend URL, authentication, logging, startup behavior, and audio devices.
- Optionally start with Windows and minimize to the system tray; do not implement it as a Windows service initially.
- Capture microphone audio and play returned TTS audio on the gaming PC, where the headset is expected to be connected.
- Package the application into a distributable Windows build and installer so Python does not need to be installed separately.

### MacBook — AI host

**FastAPI application (initially a modular monolith)**
- WebSocket telemetry ingestion.
- Session and lap lifecycle management.
- Telemetry validation, buffering, and normalization.
- Deterministic driving-analysis modules.
- Coaching-event generation and prioritization.
- Copilot orchestration and controlled context/tool access.
- Audio/STT/TTS transport endpoints.
- REST API for sessions, laps, analysis, tracks, and dashboard data.

**Frontend**
- React + TypeScript dashboard hosted by the MacBook and opened from the gaming PC browser.
- Live session view, telemetry values, lap delta, coaching observations, lap history, and copilot interaction.

**Storage**
- SQLite for sessions, laps, track/corner definitions, summaries, coaching events, and conversation metadata.
- Parquet for high-volume recorded telemetry, partitioned by date/session/lap.
- Keep raw telemetry available so analysis can be recalculated as algorithms improve.

## Proposed technology stack

| Area | Initial choice |
|---|---|
| Windows desktop application | PySide6 (Qt) |
| Gaming PC telemetry core | Python 3.12+ |
| Windows shared memory | `ctypes` + Windows mapping APIs |
| Windows executable packaging | PyInstaller (initial option; validate Qt/plugin bundling) |
| Windows installer | Inno Setup |
| Backend | FastAPI + asyncio |
| Transport | WebSockets |
| Data validation/schema | Pydantic + versioned JSON Schema |
| Numerical analysis | NumPy; SciPy where useful |
| Structured persistence | SQLite |
| Telemetry archive | Parquet |
| Frontend | React + TypeScript |
| Local LLM | Ollama |
| STT | Benchmark `faster-whisper` and Apple-Silicon-friendly alternatives |
| TTS | Benchmark Piper and suitable alternatives |
| Python dependency management | `uv` |
| Deployment | Native macOS for Ollama/audio initially; Docker Compose for suitable backend components |

### Windows application design

The gaming-PC deliverable is a standalone installable desktop application named **Assetto Corsa Coach Agent**.

- **UI:** PySide6/Qt, with a compact main window and system-tray operation.
- **Runtime:** Python telemetry core separated from UI/presentation code.
- **Main status view:** Assetto Corsa detection, backend connection, telemetry activity/rate, and microphone/output readiness.
- **Settings:** configurable backend URL/host and port, authentication, logging, launch-at-login behavior, microphone, output device, and push-to-talk.
- **Concurrency:** telemetry acquisition, WebSocket networking, and audio capture/playback must not block the Qt UI thread. Use worker threads/async tasks with safe message passing.
- **Distribution:** package the app and its runtime/dependencies into a Windows build; PyInstaller is the initial candidate. Use Inno Setup for a conventional installer.
- **User data:** store configuration and logs in an appropriate per-user application-data directory, not inside the install directory. Preserve settings and recordings during upgrades by default.
- **Process model:** run in the logged-in user's session, not as a Windows service initially, because microphone and headset access are user-session resources.
- **Destination independence:** the backend endpoint is configuration, not a hard-coded MacBook address. Changing to a VPS or another host should require a settings/configuration change, not a code change.

Keep the desktop UI thin. It should display and control the core agent rather than contain shared-memory parsing, telemetry calculations, or transport logic itself.

### MacBook model constraints

The AI host has **24 GB unified memory**. Start with one modest quantized model rather than multiple simultaneously loaded LLMs. Benchmark model variants and actual memory use before selecting a default. The analysis engine should calculate numerical metrics; the LLM should explain evidence and handle conversation. STT/TTS performance must also be benchmarked on this machine.

## Telemetry and protocol design

### Shared-memory sources

For original Assetto Corsa, the expected shared-memory mappings are:
- `acpmf_physics`
- `acpmf_graphics`
- `acpmf_static`

Do not guess structure layouts or field offsets. Verify them against the relevant Assetto Corsa SDK/header definitions or a well-maintained implementation. Validate representative values in-game before relying on them.

Use the Windows APIs:
- `OpenFileMappingW`
- `MapViewOfFile`
- `UnmapViewOfFile`
- `CloseHandle`

Read physics and graphics data independently because their update rates may differ. Preserve timestamps/source update information where available.

### Initial sampling targets

These are starting targets to measure and tune, not guaranteed game update rates:
- Physics sampling: up to approximately 100 Hz, subject to actual source update rate.
- Graphics sampling: approximately 30–60 Hz, subject to actual source update rate.
- Network publication: approximately 20 Hz.
- Agent ring buffer: approximately 30 seconds.
- Record complete laps at the available sample rate.

Avoid publishing unchanged/stale data as if it were a fresh sample. Include timestamps and sequence numbers.

### Normalized telemetry envelope

Every message should include at least:
- `schema_version`
- `game`
- `agent_id`
- `session_id` when known
- `sequence`
- `timestamp`
- `type`
- normalized payload

The telemetry model should cover, when available:
- Session/track/car identifiers and session state.
- Lap number, lap time, last/best lap time, sector and normalized lap progress.
- Speed, RPM, gear, throttle, brake, steering.
- Position and velocity data.
- Tyre, temperature, slip, suspension, and other physics values for future analysis.

Use explicit units and conventions (for example, speed in m/s or km/h, angles in radians or degrees, pedal values normalized to 0–1). Document them and do not mix units.

### Networking

- Initial LAN endpoint can be configured as a WebSocket URL, e.g. `ws://<macbook-lan-ip>:8080/ws/telemetry`.
- Include authentication even on the LAN.
- Implement heartbeat, reconnect with backoff, sequence tracking, and clear stale-connection status.
- When moving beyond the LAN, use TLS and preferably a VPN such as WireGuard. Do not expose an unauthenticated telemetry endpoint publicly.
- Keep destination URL, credentials, protocol, and publish rate in agent configuration.

## Driving-analysis design

Build deterministic modules that operate on timestamped samples and lap summaries. The LLM must not calculate lap deltas from raw streams or invent metrics.

### Lap comparison

- Store complete laps with timestamps and normalized track progress.
- Select a reference lap, initially the driver's best valid lap for the same car/track/configuration.
- Align laps on a common normalized-progress grid using interpolation.
- Calculate time delta by progress: `current_elapsed_time(progress) - reference_elapsed_time(progress)`.
- Validate lap boundaries, sample gaps, and progress monotonicity before comparison.
- Show where time is gained/lost and calculate sector/corner contributions.

### Corner analysis

For each calibrated corner, calculate initial MVP metrics:
- Braking onset position.
- Braking duration and peak brake input.
- Minimum speed and its position.
- Throttle onset position.
- Full-throttle position.
- Entry, minimum, and exit speed.
- Corner elapsed time.
- Time delta versus reference.

Start with a small number of reliable metrics. More advanced understeer/oversteer, tyre, traction, and setup analysis is later work and requires validation.

### Track/corner calibration

Normalized track progress does not automatically identify corner boundaries. For the MVP:
- Create a simple track definition file with track identifier and corner entry/apex/exit progress values.
- Begin with one track and one car.
- Calibrate boundaries using recorded laps and verify them against the track map.
- Add a basic calibration/editor workflow later.

Do not use illustrative example coordinates as production track data.

### Coaching rules

Create evidence-based rules for:
- Braking earlier/later than reference (only when conditions are comparable).
- Excessive braking or inconsistent brake release.
- Excessive coasting.
- Late throttle application.
- Lower corner-exit speed.
- Sector/lap inconsistency.

Each coaching observation should include:
- Stable event/rule identifier.
- Track/corner/lap context.
- Evidence and measured values.
- Reference values and comparison conditions.
- Confidence.
- Severity/priority.
- Estimated time impact when reliably measurable.
- Cooldown/deduplication key.

Do not tell the driver to brake later or carry more speed solely because the reference lap did so. Account for entry speed, car, track conditions, tyre state, traffic, and data quality. If comparability or confidence is insufficient, report uncertainty.

## Copilot and voice design

### Two independent flows

**Telemetry/coaching flow**
1. Receive telemetry.
2. Update rolling metrics and lap state.
3. Detect events and evaluate deterministic rules.
4. Prioritize, deduplicate, and queue coaching observations.
5. Deliver an eligible short message when safe.

**Conversation flow**
1. Capture push-to-talk audio on the gaming PC.
2. Stream audio to the MacBook.
3. Transcribe with local STT.
4. Retrieve relevant current session/lap/corner and analysis context.
5. Ask Ollama for a concise evidence-based answer.
6. Stream response text and generate TTS audio in chunks where practical.
7. Return audio to the gaming PC for headset playback.

### Context tools

Give the LLM controlled functions such as:
- `get_current_session()`
- `get_current_lap()`
- `get_current_corner()`
- `get_current_lap_delta()`
- `get_corner_comparison(corner_id)`
- `get_recent_coaching_events()`
- `get_best_lap()`

Do not give the LLM unrestricted database or raw telemetry access.

### Copilot response schema

Use structured output, validated by the backend. Suggested fields:
- `intent`
- `spoken_response`
- `severity`
- `priority`
- `evidence`
- `trigger_tts`

The copilot should:
- Never invent telemetry values.
- State uncertainty when evidence is insufficient.
- Give one actionable recommendation at a time.
- Keep spoken responses short.
- Avoid repeating the same observation.
- Avoid distracting the driver during braking or other high-workload moments.

### Audio ownership

Assume microphone and headphones are connected to the gaming PC:
- Windows agent captures microphone input.
- MacBook performs STT, LLM, and TTS.
- Windows agent plays returned audio.

Start with push-to-talk. Wake-word detection and more sophisticated audio streaming are later enhancements.

## API outline

Initial endpoints:
- `WS /ws/telemetry` — agent to backend.
- `WS /ws/audio` — audio uplink/downlink.
- `WS /ws/dashboard` — live dashboard events.
- `POST /api/sessions/start` — start/identify session.
- `GET /api/sessions/{id}` — session details.
- `GET /api/sessions/{id}/laps` — lap history.
- `GET /api/laps/{id}/analysis` — lap analysis.
- `POST /api/copilot/ask` — text-based question.
- `GET /api/tracks` — track definitions.

Keep API contracts documented and versioned.

## Repository structure

```text
assetto-corsa-coach/
├── apps/
│   ├── windows-agent/
│   │   ├── src/
│   │   │   ├── core/          # shared memory, telemetry, game detection, transport
│   │   │   ├── desktop/       # PySide6 UI, system tray, settings
│   │   │   ├── audio/         # microphone capture and speaker playback
│   │   │   └── config/
│   │   ├── tests/
│   │   └── packaging/         # PyInstaller spec and Inno Setup installer
│   ├── backend/
│   │   ├── app/
│   │   │   ├── api/
│   │   │   ├── ingestion/
│   │   │   ├── sessions/
│   │   │   ├── analysis/
│   │   │   ├── coaching/
│   │   │   ├── copilot/
│   │   │   ├── voice/
│   │   │   └── storage/
│   │   └── tests/
│   └── frontend/
│       └── src/
├── packages/
│   └── telemetry-schema/
│       └── schemas/
├── infrastructure/
│   └── docker-compose.yml
├── docs/
│   ├── architecture.md
│   └── telemetry-protocol.md
├── PLAN.md
├── context.txt
└── README.md
```

The exact layout can be adjusted to the existing repository conventions if this plan is applied to an existing codebase. The Windows agent should separate its telemetry/core modules from the PySide6 presentation layer so the reader, networking, and audio components can be tested without launching the UI.

## Implementation phases

### Phase 0 — Repository and protocol foundation
- Inspect the existing repository before adding files or choosing conventions.
- Create the project skeleton and development instructions.
- Define the first version of the normalized telemetry schema.
- Add sample/fake telemetry fixtures for backend and frontend development.
- Document units, timestamps, sequence numbers, and session/lap lifecycle.

**Exit criteria:** schema is documented, validated, and usable by a test producer and consumer.

### Phase 1 — Windows telemetry core and proof of concept
- Verify original Assetto Corsa shared-memory structure definitions for the installed game version.
- Implement Windows mapping lifecycle and safe cleanup.
- Read physics, graphics, and static mappings independently.
- Build a small Python proof of concept that logs speed, RPM, gear, throttle, brake, steering, lap number, and normalized track position.
- Record a short real session to JSONL and validate values, update rates, timestamps, and stale-data behavior.
- Keep the telemetry reader independent from any GUI framework.
- After the values are verified, define/implement normalized models and the WebSocket publisher.

**Exit criteria:** a repeatable real session produces valid diagnostic data, and the telemetry core can be tested without a desktop UI.

### Phase 2 — Windows desktop application
- Create the `Assetto Corsa Coach Agent` desktop shell with PySide6.
- Add a main status view showing game detection, backend connectivity, telemetry activity/rate, and audio readiness.
- Add a system-tray icon/menu with show/hide, connection/status information, and quit.
- Add settings for backend host/URL, port/protocol, authentication, log level/location, auto-start, microphone, speaker/output device, and push-to-talk.
- Run telemetry, networking, and audio work outside the UI thread; keep the UI responsive.
- Support graceful startup/shutdown, reconnect state, and useful error messages.
- Allow optional launch at Windows login and start minimized to tray.
- Do not run as a Windows service initially; the user session is needed for headset/microphone access.

**Exit criteria:** the app can be installed/launched, reports accurate status, stays responsive while telemetry runs, and can be configured without editing files manually.

### Phase 3 — Windows packaging and installer
- Package the application and Python runtime/dependencies into a Windows executable using PyInstaller or a better-validated equivalent.
- Verify PySide6 Qt plugins, native dependencies, and Windows API access in a clean Windows environment.
- Create an installer using Inno Setup.
- Include Start Menu shortcuts, optional desktop shortcut, optional launch-at-login, config/log directory handling, and clean uninstall behavior.
- Preserve user configuration and diagnostic recordings during upgrades/uninstall unless the user explicitly chooses to remove them.
- Document versioning and a manual update/reinstall path; automatic updates can be considered later.

**Exit criteria:** a clean Windows machine can install and run the agent without a separate Python installation, and upgrades do not silently erase configuration or logs.

### Phase 4 — MacBook ingestion and session recording
- Build FastAPI WebSocket ingestion.
- Validate protocol versions and payloads.
- Track agent connection/heartbeat/staleness.
- Implement session and lap lifecycle.
- Persist metadata in SQLite and telemetry in Parquet.
- Add replay from recorded telemetry for repeatable testing.

**Exit criteria:** a real session can be received, recorded, reloaded, and replayed without Assetto Corsa running.

### Phase 5 — Live dashboard
- Build React/TypeScript dashboard.
- Display connection status, game, track, car, lap, speed, RPM, gear, throttle, brake, and steering.
- Show session/lap history and basic lap timing.
- Consume live dashboard WebSocket updates.

**Exit criteria:** dashboard shows reliable live values and completed laps from the real game.

### Phase 6 — Lap comparison and first coaching rules
- Implement lap validation and reference-lap selection.
- Align current/reference laps by normalized progress.
- Calculate delta curve and sector differences.
- Add manual corner definitions for one track.
- Implement braking, minimum-speed, throttle-onset, and exit-speed comparisons.
- Generate evidence-backed coaching events.

**Exit criteria:** on repeatable laps, the system identifies and explains meaningful differences without false or unsupported claims.

### Phase 7 — Text copilot with Ollama
- Integrate Ollama through a provider abstraction.
- Benchmark suitable quantized models within the 24 GB memory budget.
- Implement context retrieval functions and structured output validation.
- Add conversation/session context and concise racing-engineer instructions.
- Test answers against known recorded telemetry scenarios.

**Exit criteria:** text questions are answered from actual session data, with no fabricated metrics.

### Phase 8 — Voice copilot
- Capture push-to-talk audio on Windows.
- Implement streaming or chunked audio transport.
- Integrate local STT and benchmark recognition latency/accuracy.
- Integrate local TTS and return audio to Windows.
- Add interruption, mute, cooldown, and priority controls.

**Exit criteria:** user can ask a question through the gaming headset and hear a telemetry-grounded answer.

### Phase 9 — Proactive coaching and driving-safe scheduling
- Add coaching event prioritization and deduplication.
- Add cooldowns and quiet periods.
- Initially schedule advice for straights or low-workload windows using track progress and calibrated zones.
- Add user controls for frequency and verbosity.
- Record what was spoken and why.

**Exit criteria:** useful, non-repetitive coaching is delivered without overlapping or distracting audio.

### Phase 10 — Hardening and extensibility
- Test game restarts, network loss, stale packets, malformed payloads, and storage recovery.
- Profile CPU, memory, network, and disk usage.
- Improve packaging and configuration.
- Add authentication/TLS/VPN guidance for remote deployment.
- Keep the telemetry adapter interface ready for future ACC support and cloud hosting.

**Exit criteria:** stable repeatable local sessions and a documented migration path to a remote AI host.

## MVP acceptance criteria

The MVP is complete when:
1. The Windows application installs and launches without requiring a separate Python installation.
2. Starting original Assetto Corsa allows the agent to detect the game and connect automatically.
3. The app exposes accurate game, telemetry, backend, and audio status, including from its system-tray mode.
4. The agent continuously captures and transmits valid telemetry.
5. The MacBook receives and stores a complete session and lap.
6. The dashboard displays live telemetry and lap history.
7. The user can select a valid reference lap.
8. The analysis engine identifies at least three meaningful, evidence-backed differences between comparable laps.
9. The copilot answers questions about the current lap using real telemetry context.
10. The copilot can deliver a useful proactive recommendation through the gaming headset.
11. Reconnection after a network interruption does not require restarting the game.
12. The system avoids unsupported advice and prevents repetitive or badly timed spoken coaching.

## Explicitly out of scope for the first MVP

- Assetto Corsa Competizione support.
- Cloud/VPS hosting.
- Multi-driver or multi-user support.
- Automatic setup tuning or setup recommendations.
- Advanced tyre modelling.
- Reliable understeer/oversteer diagnosis.
- Computer vision or camera-based analysis.
- Wake-word activation.
- Complex distributed microservices infrastructure.

## First concrete development task

Start with **Phase 0 and Phase 1**, but keep the first vertical slice small. The Windows GUI and installer are planned follow-on phases, not prerequisites for validating the shared-memory reader:

1. Verify the exact shared-memory structures for the installed original Assetto Corsa version.
2. Build a Python Windows proof-of-concept that reads physics and graphics data.
3. Print/log speed, RPM, gear, throttle, brake, steering, lap number, and normalized track position.
4. Record a short real session to JSONL.
5. Only after the values are verified, add the normalized schema and WebSocket publisher.

Do not start with Ollama, STT, TTS, cloud infrastructure, or advanced analysis. Reliable real telemetry is the foundation for everything else.

## Engineering risks and validation

- **Shared-memory layout mismatch:** use verified SDK definitions and test field values against the game.
- **Desktop UI blocking:** keep telemetry/network/audio workers off the PySide6 UI thread and communicate status through thread-safe signals/queues.
- **Windows packaging gaps:** test the packaged build on a clean Windows environment; explicitly verify Qt plugins, audio dependencies, permissions, and config/log paths.
- **Upgrade data loss:** keep mutable user configuration and recordings outside the application install directory and preserve them during upgrades by default.
- **Different update rates:** timestamp sources independently and detect stale samples.
- **Lap alignment errors:** validate progress wraparound, invalid laps, pits, resets, and missing samples.
- **Misleading comparisons:** compare like-for-like car/track/session conditions and record metadata.
- **False coaching:** require evidence and confidence thresholds; expose uncertainty.
- **Audio distraction:** prioritize, rate-limit, mute, and defer low-priority advice.
- **Mac memory/latency:** benchmark model size, quantization, STT/TTS, and concurrent memory use on the actual 24 GB machine.
- **Cloud exposure:** require authentication and encrypted transport outside the trusted LAN.

## Definition of success

The first meaningful success is not an AI conversation or a polished desktop UI. It is a trustworthy pipeline from the original Assetto Corsa shared memory to a recorded, replayable lap on the MacBook. Build and validate the telemetry core first, then put the PySide6 Windows application around it. Once that is reliable, lap analysis and the voice racing engineer can be built on solid ground.
