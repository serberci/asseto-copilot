# Install

Two computers. The AI host is the Mac. The agent is the Windows PC that runs the original Assetto Corsa. You can exercise the host and the dashboard on the Mac before the Windows PC is ready.

Python 3.12 or newer and [uv](https://docs.astral.sh/uv/) are required. This repository was installed and tested with Python 3.14 and uv 0.13.7. Node.js is required for the dashboard.

## AI host

From the repository root:

```sh
uv sync --all-packages
uv run pytest
```

Start the host:

```sh
export COACH_AUTH_TOKEN="choose-a-long-token"
export COACH_DATA_DIR="$PWD/data"
uv run coach-backend
```

The API listens on port 8080. Sessions, the SQLite database, and Parquet laps are stored in `data/`. If you omit `COACH_AUTH_TOKEN`, the first start writes a token to `data/auth.token` and prints that path.

Build the dashboard once:

```sh
cd apps/frontend
npm install
npm run build
```

Start the host again from the repository root. It serves `apps/frontend/dist` when that build exists. Open `http://127.0.0.1:8080/`, paste the token, and choose Connect.

For frontend development, run `npm run dev` in `apps/frontend` and open `http://127.0.0.1:5173/`. Vite forwards `/api` and `/ws` to port 8080.

## Synthetic session

This does not need the game. With the host running:

```sh
export COACH_AUTH_TOKEN="choose-a-long-token"
uv run python scripts/replay_fixture.py
```

Reload the dashboard. You should see track `synthetic-oval`, car `synthetic-car`, two valid laps (30.000 s and 30.400 s), a delta near `+0.400`, and coaching lines. Ask `where am I losing time`. The answer quotes the recorded loss and names the model `deterministic-explainer`.

`synthetic-oval` is not a real circuit. Do not copy its corner progress onto a real track.

## Windows agent

On the gaming PC, from this repository:

```sh
uv sync --all-packages --package coach-agent --extra desktop
```

Put the same token and the Mac's address in the agent settings. The file is created on first launch:

- Windows: `%APPDATA%\AssettoCorsaCoachAgent\settings.json`
- macOS, for development: `~/Library/Application Support/AssettoCorsaCoachAgent/settings.json`

Set `backend_url` to `ws://<mac-lan-ip>:8080/ws/telemetry` and `auth_token` to the host token. You can also set them in the desktop window. A change of address is used after the agent restarts.

Check the page layout without the game:

```sh
uv run coach-agent --diagnose --fixture fixtures/page-sample.json
```

A live reading, on Windows, with Assetto Corsa running:

```sh
uv run coach-agent --diagnose
```

The process name the agent looks for is `acs.exe`. Compare the printed speed, rpm, gear, throttle, brake, lap count, and track position with the game before you trust coaching. When they match, create an empty file named `layout-confirmed` in the agent settings directory. The desktop window then stops showing the confirmation warning.

Run the window:

```sh
uv run coach-agent
```

Closing the window hides it to the tray. Quit is on the tray menu. `--minimized` starts in the tray. The telemetry loop runs off the UI thread.

Headless, for a machine where you only want the reader:

```sh
uv run coach-agent --headless
```

Record a diagnostic JSONL on Windows:

```sh
uv run coach-agent --record session.jsonl --seconds 30
```

The lines contain the normalized message and the raw game fields `speedKmh`, `rpms`, `gear`, `gas`, `brake`, `steerAngle`, `completedLaps`, and `normalizedCarPosition`.

## First live session

1. Host running, token set, dashboard open from the gaming PC's browser at `http://<mac-lan-ip>:8080/`.
2. Agent settings point at that host.
3. Drive. The dashboard speed, in km/h, should match the game. Gear `R` is raw gear 0, `N` is 1, and `1` is 2.
4. Complete two clean laps. They appear in the lap table after the game increments the completed-lap counter.
5. Pick a reference lap in the table if you do not want the fastest valid lap.
6. Add a calibrated track file before expecting corner coaching. Copy `apps/backend/coach_backend/track_data/bundled/_template.json` to `data/tracks/<track-id>.json`. The `track_id` must be the game's track name. Set `calibrated` to `true` only after the entry, apex, and exit progress values have been checked against a recorded lap. Files with `calibrated: false` are ignored.

## Optional language model

Ollama stays on the Mac, not in Docker. After you have chosen and benchmarked one quantized model that fits in 24 GB together with the rest of the host:

```sh
export COACH_OLLAMA_HOST="http://127.0.0.1:11434"
export COACH_OLLAMA_MODEL="the-model-you-benchmarked"
```

The default name in settings, `llama3.2:3b`, is a candidate, not a measured choice. Answers are still checked against the evidence. A number that is not in the context is not spoken; the explainer answers instead.

## Voice

The headset stays on the gaming PC. Push-to-talk state is implemented. The host's `/ws/audio` socket accepts a PCM clip and, today, returns `stt_unavailable`. Wire a local speech engine only after you have benchmarked it on this Mac. Do not point this socket at a cloud recognizer if the point of the system is to stay local.

## Docker

The API can run in Docker. Ollama does not.

```sh
export COACH_AUTH_TOKEN="choose-a-long-token"
docker compose -f infrastructure/docker-compose.yml up --build
```

The image does not include the dashboard build. Serve the dashboard from the Mac, or set the image up with `apps/frontend/dist` mounted and `COACH_STATIC_DIR` pointed at it.

## Windows installer

Build this on Windows, after the live shared-memory check:

```sh
uv sync --all-packages --package coach-agent --extra desktop
uv run --with pyinstaller pyinstaller --noconfirm --distpath apps/windows-agent/dist --workpath apps/windows-agent/build apps/windows-agent/packaging/coach-agent.spec
```

Compile `apps/windows-agent/packaging/installer.iss` with Inno Setup. The installer is written to `apps/windows-agent/packaging/Output/AssettoCorsaCoachAgent-Setup.exe`. It does not delete `%APPDATA%\AssettoCorsaCoachAgent` unless you confirm that at uninstall time. That folder holds settings and diagnostic recordings.

GitHub Actions can build the same installer on a Windows runner. The workflow is `.github/workflows/windows-installer.yml`. It runs on a manual dispatch and when agent, schema, or lock files change on `main`. The setup file is the artifact `AssettoCorsaCoachAgent-Setup`, kept for 14 days. That build has not seen a live Assetto Corsa session.

There is no automatic update yet. Install the new build over the old one and leave the AppData folder in place.
