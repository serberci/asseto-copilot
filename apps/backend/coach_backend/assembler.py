"""Lap boundaries. A lap closes when Assetto Corsa increments completed laps."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from telemetry_schema.messages import TelemetryMessage


@dataclass
class CompletedLap:
    lap_number: int
    samples: list[TelemetryMessage]
    lap_time_ms: int | None
    invalid_reasons: list[str]
    started_at: datetime
    ended_at: datetime

    @property
    def valid(self) -> bool:
        return not self.invalid_reasons


@dataclass
class LapAssembler:
    minimum_samples: int = 20
    _open: list[TelemetryMessage] = field(default_factory=list)
    _last_completed: int | None = None
    _last_progress: float | None = None
    _last_time: datetime | None = None
    _gap: bool = False
    _reset: bool = False

    def add(self, message: TelemetryMessage) -> CompletedLap | None:
        payload = message.payload
        if payload.session_status != "live":
            return None
        if self._last_completed is not None and payload.completed_laps > self._last_completed:
            finished = self._close(payload.last_lap_time_ms, message.timestamp)
            self._last_completed = payload.completed_laps
            self._open = [message]
            self._last_progress = payload.normalized_progress
            self._last_time = message.timestamp
            self._gap = False
            self._reset = False
            return finished
        if (
            self._open
            and self._last_progress is not None
            and payload.normalized_progress < self._last_progress - 0.2
        ):
            self._reset = True
            finished = self._close(None, message.timestamp)
            self._last_completed = payload.completed_laps
            self._open = [message]
            self._last_progress = payload.normalized_progress
            self._last_time = message.timestamp
            self._gap = False
            self._reset = False
            return finished
        if self._last_time is not None and (message.timestamp - self._last_time).total_seconds() > 1:
            self._gap = True
        self._open.append(message)
        self._last_progress = payload.normalized_progress
        self._last_time = message.timestamp
        if self._last_completed is None:
            self._last_completed = payload.completed_laps
        return None

    def _close(self, lap_time_ms: int | None, ended_at: datetime) -> CompletedLap:
        samples = list(self._open)
        reasons: list[str] = []
        if len(samples) < self.minimum_samples:
            reasons.append("too_few_samples")
        progresses = [sample.payload.normalized_progress for sample in samples]
        if not progresses or min(progresses) > 0.05 or max(progresses) < 0.95:
            reasons.append("partial")
        if samples and sum(1 for sample in samples if sample.payload.in_pit) * 2 > len(samples):
            reasons.append("in_pit")
        if self._gap:
            reasons.append("sample_gap")
        if self._reset:
            reasons.append("progress_reset")
        lap_number = samples[-1].payload.lap_number if samples else 0
        started = samples[0].timestamp if samples else ended_at
        self._open = []
        return CompletedLap(
            lap_number=lap_number,
            samples=samples,
            lap_time_ms=lap_time_ms,
            invalid_reasons=reasons,
            started_at=started,
            ended_at=ended_at,
        )
