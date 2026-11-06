"""Track definitions. Uncalibrated files are never used for coaching."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, model_validator

BUNDLED = Path(__file__).resolve().parent / "track_data" / "bundled"


class Corner(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=1, max_length=80)
    entry: float = Field(ge=0, le=1)
    apex: float = Field(ge=0, le=1)
    exit: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def increasing(self) -> Corner:
        if not self.entry < self.apex < self.exit:
            raise ValueError(f"corner {self.id} progress must increase from entry to exit")
        return self


class Track(BaseModel):
    model_config = ConfigDict(extra="forbid")

    track_id: str = Field(min_length=1, max_length=80)
    calibrated: bool
    note: str = ""
    corners: list[Corner]


class TrackLibrary:
    def __init__(self, data_dir: Path) -> None:
        self.user_dir = data_dir / "tracks"
        self.user_dir.mkdir(parents=True, exist_ok=True)

    def get(self, track_id: str) -> Track | None:
        for directory in (self.user_dir, BUNDLED):
            path = directory / f"{track_id}.json"
            if not path.exists():
                continue
            track = Track.model_validate(json.loads(path.read_text(encoding="utf-8")))
            if track.track_id != track_id or not track.calibrated:
                return None
            return track
        return None

    def list_tracks(self) -> list[dict]:
        found: dict[str, dict] = {}
        for directory in (BUNDLED, self.user_dir):
            if not directory.exists():
                continue
            for path in sorted(directory.glob("*.json")):
                if path.name.startswith("_"):
                    continue
                track = Track.model_validate(json.loads(path.read_text(encoding="utf-8")))
                found[track.track_id] = {
                    "track_id": track.track_id,
                    "calibrated": track.calibrated,
                    "corners": len(track.corners),
                    "note": track.note,
                }
        return list(found.values())
