"""Telemetry loop. The UI calls `tick`; it does not read shared memory itself."""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from threading import Lock

from telemetry_schema.messages import SCHEMA_VERSION, HeartbeatMessage, HelloMessage, TelemetryMessage
from telemetry_schema.models import HeartbeatPayload, HelloPayload

from coach_agent import __version__
from coach_agent.config.settings import AgentSettings
from coach_agent.core.layouts import SharedMemoryError
from coach_agent.core.link import OutboundLink
from coach_agent.core.mapping import SharedMemoryUnavailable
from coach_agent.core.normalize import NormalizationError, normalize
from coach_agent.core.reader import SnapshotReader
from coach_agent.core.recorder import JsonlRecorder
from coach_agent.core.ring_buffer import RingBuffer


class Clock:
    def mono(self) -> float:
        return time.monotonic()

    def wall(self) -> datetime:
        return datetime.now(timezone.utc)


@dataclass
class AgentStatus:
    game_running: bool = False
    shared_memory_open: bool = False
    backend: str = "disconnected"
    physics_rate_hz: float = 0
    graphics_rate_hz: float = 0
    publish_rate_hz: float = 0
    last_error: str | None = None
    fixture_mode: bool = False
    layout_confirmed: bool = False


class CoachAgent:
    def __init__(
        self,
        settings: AgentSettings,
        link: OutboundLink,
        open_reader: callable,
        *,
        clock: Clock | None = None,
        game_running=None,
        recorder: JsonlRecorder | None = None,
        fixture_mode: bool = False,
        layout_confirmed: bool = False,
    ) -> None:
        self.settings = settings
        self.link = link
        self._open_reader = open_reader
        self._clock = clock or Clock()
        self._game_running = game_running or (lambda: False)
        self._recorder = recorder
        self._reader: SnapshotReader | None = None
        self.ring = RingBuffer(capacity=int(settings.physics_hz * 30))
        self.sequence = 0
        self._lock = Lock()
        self._last_publish = -1_000.0
        self._last_heartbeat = -1_000.0
        self._physics_times: deque[float] = deque()
        self._graphics_times: deque[float] = deque()
        self._publish_times: deque[float] = deque()
        self._sample_error: str | None = None
        self.status = AgentStatus(fixture_mode=fixture_mode, layout_confirmed=layout_confirmed)

    def hello(self) -> HelloMessage:
        base = self._base(self._clock.wall())
        return HelloMessage(
            **base,
            type="hello",
            payload=HelloPayload(
                agent_name="Assetto Corsa Coach Agent",
                agent_version=__version__,
                capabilities=["telemetry", "push_to_talk"],
            ),
        )

    def tick(self) -> None:
        now = self._clock.mono()
        wall = self._clock.wall()
        running = True if self.status.fixture_mode else bool(self._game_running())
        self.status.game_running = running
        self.status.backend = self.link.state
        if not running:
            self._close_reader()
            self.status.shared_memory_open = False
            self._sample_error = None
            self._update_error()
            self._heartbeat(now, wall)
            return
        try:
            snapshot = self._ensure_reader().read(wall)
        except (SharedMemoryUnavailable, SharedMemoryError) as exc:
            self._close_reader()
            self.status.shared_memory_open = False
            self._sample_error = str(exc)
            self._update_error()
            self._heartbeat(now, wall)
            return
        self.status.shared_memory_open = True
        fresh_physics = not snapshot.physics.stale
        fresh_graphics = not snapshot.graphics.stale
        if fresh_physics:
            self._physics_times.append(now)
        if fresh_graphics:
            self._graphics_times.append(now)
        self._trim(self._physics_times, now)
        self._trim(self._graphics_times, now)
        self.status.physics_rate_hz = float(len(self._physics_times))
        self.status.graphics_rate_hz = float(len(self._graphics_times))
        if not fresh_physics and not fresh_graphics:
            self._update_error()
            self._heartbeat(now, wall)
            return
        try:
            payload = normalize(snapshot)
        except NormalizationError as exc:
            self._sample_error = str(exc)
            self._update_error()
            self._heartbeat(now, wall)
            return
        self._sample_error = None
        self.ring.append(payload)
        should_publish = now - self._last_publish >= 1 / self.settings.publish_hz
        if self._recorder is not None or should_publish:
            message = TelemetryMessage(**self._base(wall), type="telemetry", payload=payload)
            if self._recorder is not None:
                self._recorder.record(message, snapshot)
            if should_publish:
                self.link.submit(message)
                self._last_publish = now
                self._publish_times.append(now)
        self._trim(self._publish_times, now)
        self.status.publish_rate_hz = float(len(self._publish_times))
        self._update_error()
        self._heartbeat(now, wall)

    def close(self) -> None:
        self._close_reader()
        self.link.stop()

    def _ensure_reader(self) -> SnapshotReader:
        if self._reader is None:
            self._reader = self._open_reader()
        return self._reader

    def _close_reader(self) -> None:
        if self._reader is not None:
            self._reader.close()
            self._reader = None

    def _heartbeat(self, now: float, wall: datetime) -> None:
        if now - self._last_heartbeat < self.settings.heartbeat_s:
            return
        self._last_heartbeat = now
        self.link.submit(
            HeartbeatMessage(
                **self._base(wall),
                type="heartbeat",
                payload=HeartbeatPayload(
                    physics_rate_hz=self.status.physics_rate_hz,
                    graphics_rate_hz=self.status.graphics_rate_hz,
                    publish_rate_hz=self.status.publish_rate_hz,
                    game_running=self.status.game_running,
                    shared_memory_open=self.status.shared_memory_open,
                    backend_connected=self.link.state == "connected",
                    last_error=self.status.last_error,
                ),
            )
        )

    def _base(self, wall: datetime) -> dict:
        with self._lock:
            self.sequence += 1
            sequence = self.sequence
        return {
            "schema_version": SCHEMA_VERSION,
            "game": "assetto_corsa",
            "agent_id": self.settings.agent_id,
            "session_id": self.link.session_id,
            "sequence": sequence,
            "timestamp": wall,
        }

    def _update_error(self) -> None:
        self.status.last_error = self.link.last_error or self._sample_error

    @staticmethod
    def _trim(times: deque[float], now: float) -> None:
        while times and now - times[0] > 1:
            times.popleft()
