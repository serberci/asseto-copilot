# Run and check

Commands are from the repository root unless noted. Details and the Windows installer are in [../INSTALL.md](../INSTALL.md).

```sh
uv sync --all-packages
uv run pytest
cd apps/frontend && npm install && npm run build
```

Host and synthetic session:

```sh
export COACH_AUTH_TOKEN="choose-a-long-token"
export COACH_DATA_DIR="$PWD/data"
uv run coach-backend
```

In another shell, with the same token:

```sh
uv run python scripts/replay_fixture.py
```

Shared-memory image, no game:

```sh
uv run coach-agent --diagnose --fixture fixtures/page-sample.json
```

Expected lines include `physics page 580 bytes`, `speed_kmh=180.0`, `gear=4`, `track='imola'`.

Desktop extra, on the machine that will show the window:

```sh
uv sync --all-packages --package coach-agent --extra desktop
uv run coach-agent
```

`make test` runs pytest. `make backend` starts the host. `make fixture` replays the synthetic session and needs `COACH_AUTH_TOKEN`.

The Windows installer workflow runs on `windows-latest`. It installs the agent with the desktop extra, runs PyInstaller, compiles the Inno Setup script, and uploads `AssettoCorsaCoachAgent-Setup.exe`. Start it with `gh workflow run "Windows installer"` or from the Actions tab. The artifact is untested against a live game session.

Data written at runtime is under `data/` or the agent settings directory. Neither belongs in git.
