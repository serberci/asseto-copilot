"""Deterministic lap alignment. The language model does not compute these numbers."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class LapSeries:
    progress: np.ndarray
    elapsed_s: np.ndarray
    speed_mps: np.ndarray
    throttle: np.ndarray
    brake: np.ndarray


@dataclass(frozen=True)
class CornerMetrics:
    corner_id: str
    name: str
    braking_onset: float | None
    peak_brake: float | None
    min_speed_mps: float | None
    min_speed_progress: float | None
    throttle_onset: float | None
    full_throttle: float | None
    entry_speed_mps: float | None
    exit_speed_mps: float | None
    corner_time_s: float | None
    coast_s: float | None


def series_from_rows(rows: list[dict]) -> LapSeries | None:
    ordered = sorted(rows, key=lambda row: float(row["elapsed_s"]))
    progress: list[float] = []
    elapsed: list[float] = []
    speed: list[float] = []
    throttle: list[float] = []
    brake: list[float] = []
    last = -1.0
    for row in ordered:
        point = float(row["normalized_progress"])
        if point <= last:
            continue
        progress.append(point)
        elapsed.append(float(row["elapsed_s"]))
        speed.append(float(row["speed_mps"]))
        throttle.append(float(row["throttle"]))
        brake.append(float(row["brake"]))
        last = point
    if len(progress) < 2:
        return None
    return LapSeries(
        progress=np.asarray(progress),
        elapsed_s=np.asarray(elapsed),
        speed_mps=np.asarray(speed),
        throttle=np.asarray(throttle),
        brake=np.asarray(brake),
    )


def _interp(grid: np.ndarray, series: LapSeries, values: np.ndarray) -> np.ndarray:
    sampled = np.interp(grid, series.progress, values)
    outside = (grid < series.progress[0]) | (grid > series.progress[-1])
    sampled = sampled.astype(float)
    sampled[outside] = np.nan
    return sampled


def delta_curve(current: LapSeries, reference: LapSeries, points: int = 50) -> list[dict]:
    grid = np.linspace(0, 1, points)
    current_time = _interp(grid, current, current.elapsed_s)
    reference_time = _interp(grid, reference, reference.elapsed_s)
    delta = current_time - reference_time
    curve = []
    for progress, value in zip(grid, delta, strict=True):
        curve.append(
            {
                "progress": round(float(progress), 4),
                "delta_s": None if np.isnan(value) else round(float(value), 4),
            }
        )
    return curve


def _first_progress(series: LapSeries, mask: np.ndarray) -> float | None:
    if not mask.any():
        return None
    return float(series.progress[mask][0])


def _value_at(series: LapSeries, values: np.ndarray, progress: float) -> float | None:
    if progress < series.progress[0] or progress > series.progress[-1]:
        return None
    return float(np.interp(progress, series.progress, values))


def corner_metrics(series: LapSeries, corner) -> CornerMetrics:
    window = (series.progress >= corner.entry) & (series.progress <= corner.exit)
    braking = window & (series.brake >= 0.05)
    onset = _first_progress(series, braking)
    if braking.any():
        release_index = np.where(braking)[0][-1] + 1
        after_brake = np.zeros(len(series.progress), dtype=bool)
        after_brake[release_index:] = True
    else:
        after_brake = window
    throttle_on = after_brake & window & (series.throttle >= 0.1) & (series.brake < 0.05)
    full = window & (series.throttle >= 0.98)
    peak = float(series.brake[window].max()) if window.any() else None
    if window.any():
        min_index = int(np.argmin(series.speed_mps[window]))
        window_index = np.where(window)[0][min_index]
        min_speed = float(series.speed_mps[window_index])
        min_progress = float(series.progress[window_index])
    else:
        min_speed = None
        min_progress = None
    entry_speed = _value_at(series, series.speed_mps, corner.entry)
    exit_speed = _value_at(series, series.speed_mps, corner.exit)
    entry_time = _value_at(series, series.elapsed_s, corner.entry)
    exit_time = _value_at(series, series.elapsed_s, corner.exit)
    corner_time = None if entry_time is None or exit_time is None else exit_time - entry_time
    throttle_progress = _first_progress(series, throttle_on)
    coast = None
    if onset is not None and throttle_progress is not None:
        release = _first_progress(series, (series.progress >= onset) & (series.brake < 0.05))
        if release is not None:
            release_time = _value_at(series, series.elapsed_s, release)
            throttle_time = _value_at(series, series.elapsed_s, throttle_progress)
            if release_time is not None and throttle_time is not None:
                coast = max(0.0, throttle_time - release_time)
    return CornerMetrics(
        corner_id=corner.id,
        name=corner.name,
        braking_onset=onset,
        peak_brake=peak,
        min_speed_mps=min_speed,
        min_speed_progress=min_progress,
        throttle_onset=throttle_progress,
        full_throttle=_first_progress(series, full),
        entry_speed_mps=entry_speed,
        exit_speed_mps=exit_speed,
        corner_time_s=corner_time,
        coast_s=coast,
    )


def time_impact(current: LapSeries, reference: LapSeries, entry: float, exit_: float) -> float | None:
    current_entry = _value_at(current, current.elapsed_s, entry)
    current_exit = _value_at(current, current.elapsed_s, exit_)
    reference_entry = _value_at(reference, reference.elapsed_s, entry)
    reference_exit = _value_at(reference, reference.elapsed_s, exit_)
    if None in (current_entry, current_exit, reference_entry, reference_exit):
        return None
    return (current_exit - current_entry) - (reference_exit - reference_entry)
