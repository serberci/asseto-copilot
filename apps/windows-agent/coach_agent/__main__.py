"""Command line for the telemetry core and, on Windows, the desktop shell."""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from coach_agent.config.settings import AgentSettings, app_data_dir
from coach_agent.core.agent import Clock, CoachAgent
from coach_agent.core.game import game_is_running, list_process_names
from coach_agent.core.layouts import GRAPHICS_BYTES, PHYSICS_BYTES, STATIC_BYTES
from coach_agent.core.link import OutboundLink, websocket_connector
from coach_agent.core.mapping import BufferSharedMemory, WindowsSharedMemory
from coach_agent.core.reader import SnapshotReader
from coach_agent.core.recorder import JsonlRecorder


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="coach-agent", description="Assetto Corsa Coach Agent")
    parser.add_argument("--headless", action="store_true", help="Run the telemetry core without the desktop window")
    parser.add_argument("--minimized", action="store_true", help="Start in the system tray")
    parser.add_argument("--fixture", type=Path, help="Read page images from a JSON fixture instead of shared memory")
    parser.add_argument("--diagnose", action="store_true", help="Print layout sizes and one live sample if the game is running")
    parser.add_argument("--record", type=Path, help="Write diagnostic JSONL and exit")
    parser.add_argument("--seconds", type=float, default=10)
    parser.add_argument("--settings-dir", type=Path)
    args = parser.parse_args(argv)

    settings_dir = args.settings_dir or app_data_dir()
    settings = AgentSettings.load(settings_dir)
    logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO), format="%(levelname)s %(message)s")
    if args.diagnose:
        return diagnose(settings, args.fixture, settings_dir)
    if args.record:
        return record(settings, args.record, args.seconds, args.fixture, settings_dir)
    if args.headless or args.fixture:
        return run_headless(settings, args.fixture, settings_dir)
    return run_desktop(settings, args.minimized or settings.start_minimized, settings_dir)


def diagnose(settings: AgentSettings, fixture: Path | None, settings_dir: Path) -> int:
    print(f"physics page {PHYSICS_BYTES} bytes")
    print(f"graphics page {GRAPHICS_BYTES} bytes")
    print(f"static page {STATIC_BYTES} bytes")
    print(f"settings {settings_dir / 'settings.json'}")
    print(f"backend {settings.backend_url}")
    if fixture is None and sys.platform != "win32":
        print("shared memory is available on Windows while Assetto Corsa (acs.exe) is running")
        return 0
    try:
        reader = open_reader(fixture)()
        snapshot = reader.read(datetime.now(timezone.utc))
    except Exception as exc:
        print(f"sample unavailable: {exc}")
        return 1
    physics = snapshot.physics
    graphics = snapshot.graphics
    print(
        "speed_kmh={:.1f} rpm={} gear={} throttle={:.2f} brake={:.2f} steer={:.3f} laps={} progress={:.4f}".format(
            physics.speed_kmh,
            physics.rpms,
            physics.gear,
            physics.gas,
            physics.brake,
            physics.steer_angle,
            graphics.completed_laps,
            graphics.normalized_position,
        )
    )
    print(f"track={snapshot.static.track!r} car={snapshot.static.car_model!r}")
    reader.close()
    return 0


def record(settings: AgentSettings, output: Path, seconds: float, fixture: Path | None, settings_dir: Path) -> int:
    agent = build_agent(settings, fixture, output, settings_dir)
    clock = time.monotonic()
    deadline = clock + seconds
    while time.monotonic() < deadline:
        agent.tick()
        agent.link.pump()
        time.sleep(1 / settings.physics_hz)
    agent.close()
    print(f"wrote {output}")
    return 0


def run_headless(settings: AgentSettings, fixture: Path | None, settings_dir: Path) -> int:
    agent = build_agent(settings, fixture, None, settings_dir)
    agent.link.start()
    try:
        while True:
            agent.tick()
            time.sleep(1 / settings.physics_hz)
    except KeyboardInterrupt:
        agent.close()
    return 0


def run_desktop(settings: AgentSettings, minimized: bool, settings_dir: Path) -> int:
    try:
        from coach_agent.desktop.app import run_app

        return run_app(settings, minimized=minimized, settings_dir=settings_dir)
    except ImportError as exc:
        print("The desktop extra is not installed. From the repository root run:")
        print("uv sync --all-packages --package coach-agent --extra desktop")
        print(exc)
        return 1


def build_agent(settings: AgentSettings, fixture: Path | None, record_path: Path | None, home: Path) -> CoachAgent:
    recorder = None
    if record_path is not None:
        recorder = JsonlRecorder(record_path)
    elif settings.record_jsonl and fixture is None:
        recorder = JsonlRecorder(home / "recordings" / "latest.jsonl")

    def hello_factory():
        return agent.hello()

    link = OutboundLink(
        connector=websocket_connector(settings.backend_url, settings.auth_token),
        hello_factory=hello_factory,
    )
    agent = CoachAgent(
        settings,
        link,
        open_reader(fixture),
        clock=Clock(),
        game_running=lambda: game_is_running(list_process_names()),
        recorder=recorder,
        fixture_mode=fixture is not None,
        layout_confirmed=(home / "layout-confirmed").exists(),
    )
    return agent


def open_reader(fixture: Path | None):
    if fixture is None:
        def open_live() -> SnapshotReader:
            return SnapshotReader(WindowsSharedMemory())

        return open_live

    payload = json.loads(fixture.read_text(encoding="utf-8"))

    def open_fixture() -> SnapshotReader:
        return SnapshotReader(
            BufferSharedMemory(
                physics=bytes.fromhex(payload["physics"]),
                graphics=bytes.fromhex(payload["graphics"]),
                static=bytes.fromhex(payload["static"]),
            )
        )

    return open_fixture


if __name__ == "__main__":
    raise SystemExit(main())
