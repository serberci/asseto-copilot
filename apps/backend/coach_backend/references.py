"""Reference laps. Pro files are local data, never a download from another site.

The bundled McLaren file is a synthetic test lap. It uses the same channel
names a Competizione trace would use, and it is not a recorded Spa lap.
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

BUNDLED = Path(__file__).resolve().parent / "track_data" / "references"
SLIP_FLAG = 1.0


class ReferenceSample(BaseModel):
    model_config = ConfigDict(extra="forbid")

    progress: float = Field(ge=0, le=1)
    speed_mps: float = Field(ge=0)
    throttle: float = Field(ge=0, le=1)
    brake: float = Field(ge=0, le=1)
    steering: float
    gear: int = Field(ge=0, le=15)
    rpm: int = Field(ge=0)
    slip: float = 0
    tyres_out: int = Field(default=0, ge=0, le=4)


class ReferenceLap(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    game: str
    track_id: str
    car_model: str
    driver_class: str
    source: str
    lap_time_ms: int = Field(ge=0)
    note: str
    samples: list[ReferenceSample] = Field(min_length=2)


class ReferenceLibrary:
    def __init__(self, directory: Path | None = None) -> None:
        self.directory = directory or BUNDLED
        self._laps = _load(self.directory)

    def list_laps(self) -> list[dict]:
        return [_public(lap) for lap in self._laps]

    def pro_for(self, game: str, track_id: str, car_model: str) -> ReferenceLap | None:
        matches = [
            lap
            for lap in self._laps
            if lap.driver_class == "pro"
            and lap.game == game
            and lap.track_id == track_id
            and lap.car_model == car_model
        ]
        if not matches:
            return None
        return min(matches, key=lambda lap: lap.lap_time_ms)

    def get(self, reference_id: str) -> ReferenceLap | None:
        return next((lap for lap in self._laps if lap.id == reference_id), None)


def synthetic_samples(*, brake_at: float, slip_at: float | None = None) -> list[dict]:
    """A closed oval-shaped trace. The progress values are not Spa corners."""

    samples = []
    for step in range(51):
        progress = round(step / 50, 2)
        braking = brake_at <= progress < brake_at + 0.06
        if progress < brake_at:
            speed = 50.0
        elif progress < brake_at + 0.06:
            speed = 50.0 - (progress - brake_at) / 0.06 * 15.0
        elif progress < 0.60:
            speed = 35.0 + (progress - (brake_at + 0.06)) / max(0.01, 0.60 - (brake_at + 0.06)) * 13.0
        else:
            speed = 48.0 if brake_at > 0.44 else 44.0
        samples.append(
            {
                "progress": progress,
                "speed_mps": round(speed, 3),
                "throttle": 0.0 if progress < brake_at + 0.08 else 1.0,
                "brake": 0.9 if braking else 0.0,
                "steering": 0.2 if 0.40 <= progress <= 0.60 else 0.0,
                "gear": 4,
                "rpm": 7000,
                "slip": 1.5 if slip_at is not None and abs(progress - slip_at) < 0.001 else 0.02,
                "tyres_out": 0,
            }
        )
    return samples


def compare_pro(
    rows: list[dict],
    reference: ReferenceLap,
    *,
    game: str,
    track_id: str,
    car_model: str,
    lap_time_ms: int | None,
) -> dict:
    identity = {
        "reference_id": reference.id,
        "source": reference.source,
        "game": reference.game,
        "track_id": reference.track_id,
        "car_model": reference.car_model,
        "lap_time_ms": reference.lap_time_ms,
        "note": reference.note,
    }
    if game != reference.game or track_id != reference.track_id or car_model != reference.car_model:
        return {
            "available": False,
            "reason": "different_car_or_track",
            "recommendation_allowed": False,
            "spoken_text": (
                f"The pro file is {reference.game} {reference.track_id} {reference.car_model}. "
                "It is not a brake or throttle target for this lap."
            ),
            **identity,
            "tips": [],
        }
    current_onset, current_entry = _onset(rows, "normalized_progress")
    reference_onset, reference_entry = _onset([sample.model_dump() for sample in reference.samples], "progress")
    loss = None if lap_time_ms is None else round((lap_time_ms - reference.lap_time_ms) / 1000, 3)
    comparable = (
        current_entry is not None
        and reference_entry is not None
        and reference_entry > 1
        and abs(current_entry - reference_entry) / reference_entry <= 0.03
    )
    tips = [_steering_tip(rows, reference)]
    if current_onset is None or reference_onset is None:
        spoken = "The brake trace does not contain an onset to compare."
        allowed = False
    elif not comparable:
        spoken = (
            f"Braking onset is {current_onset:.2f} versus the pro file {reference_onset:.2f}. "
            "Entry speed does not match, so this is not a brake target."
        )
        allowed = False
    elif current_onset < reference_onset - 0.004 and loss is not None and loss > 0:
        spoken = (
            f"You braked earlier than the pro file and lost {loss:.2f} s. "
            f"Entry speed matches. The pro onset was {reference_onset:.2f}."
        )
        allowed = True
    else:
        spoken = (
            f"Braking onset is {current_onset:.2f} and the pro file is {reference_onset:.2f}. "
            "That difference is not a reason to brake later."
        )
        allowed = False
    tips.insert(
        0,
        {
            "rule_id": "pro_brake_point",
            "recommendation_allowed": allowed,
            "spoken_text": spoken,
            "evidence": {"braking_onset": current_onset, "entry_speed_mps": current_entry, "time_loss_s": loss},
            "reference": {"braking_onset": reference_onset, "entry_speed_mps": reference_entry},
        },
    )
    return {
        "available": True,
        "reason": None,
        "recommendation_allowed": allowed,
        "spoken_text": spoken,
        "time_loss_s": loss,
        **identity,
        "tips": tips,
    }


def grip_flags(payloads: list[dict]) -> list[dict]:
    """Record raw slip and tyres off track. Neither one is a driving instruction."""

    peak_slip = 0.0
    slip_progress = None
    tyres = 0
    tyres_progress = None
    for payload in payloads:
        wheels = payload.get("wheels") or []
        slip = payload.get("slip")
        if slip is None and wheels:
            slip = max(float(wheel.get("slip") or 0) for wheel in wheels)
        slip = float(slip or 0)
        progress = payload.get("normalized_progress", payload.get("progress"))
        if slip > peak_slip:
            peak_slip = slip
            slip_progress = progress
        out = int(payload.get("number_of_tyres_out") or payload.get("tyres_out") or 0)
        if out > tyres:
            tyres = out
            tyres_progress = progress
    flags = []
    if peak_slip >= SLIP_FLAG:
        flags.append(
            {
                "kind": "high_slip",
                "recommendation_allowed": False,
                "progress": slip_progress,
                "slip": round(peak_slip, 3),
                "spoken_text": (
                    f"Raw wheel slip reached {peak_slip:.2f} at progress {slip_progress}. "
                    "It is stored for later and is not a driving instruction."
                ),
            }
        )
    if tyres:
        flags.append(
            {
                "kind": "tyres_out",
                "recommendation_allowed": False,
                "progress": tyres_progress,
                "tyres_out": tyres,
                "spoken_text": f"{tyres} tyres were outside the track limits. That is recorded, not a line to chase.",
            }
        )
    return flags


def _onset(rows: list[dict], progress_key: str) -> tuple[float | None, float | None]:
    for row in rows:
        progress = float(row[progress_key])
        if progress >= 0.2 and float(row["brake"]) >= 0.05:
            return progress, float(row["speed_mps"])
    return None, None


def _steering_tip(rows: list[dict], reference: ReferenceLap) -> dict:
    current = max((abs(float(row["steering"])) for row in rows), default=0.0)
    reference_peak = max(abs(sample.steering) for sample in reference.samples)
    return {
        "rule_id": "steering_peak",
        "recommendation_allowed": False,
        "spoken_text": (
            f"Peak steering on this lap is {current:.3f}. The pro file peaks at {reference_peak:.3f}. "
            "Steering is recorded and is not a recommendation."
        ),
        "evidence": {"peak_steering": round(current, 3)},
        "reference": {"peak_steering": round(reference_peak, 3)},
    }


def _load(directory: Path) -> list[ReferenceLap]:
    if not directory.exists():
        return []
    laps = []
    for path in sorted(directory.glob("*.json")):
        if path.name.startswith("_"):
            continue
        laps.append(ReferenceLap.model_validate(json.loads(path.read_text(encoding="utf-8"))))
    return laps


def _public(lap: ReferenceLap) -> dict:
    return {
        "id": lap.id,
        "game": lap.game,
        "track_id": lap.track_id,
        "car_model": lap.car_model,
        "driver_class": lap.driver_class,
        "source": lap.source,
        "lap_time_ms": lap.lap_time_ms,
        "note": lap.note,
        "samples": len(lap.samples),
    }
