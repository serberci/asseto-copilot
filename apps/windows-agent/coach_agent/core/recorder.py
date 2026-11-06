"""Append diagnostic JSONL outside the install directory."""

from __future__ import annotations

import json
from pathlib import Path

from telemetry_schema.messages import TelemetryMessage

from coach_agent.core.reader import Snapshot


class JsonlRecorder:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def record(self, message: TelemetryMessage, snapshot: Snapshot) -> None:
        physics = snapshot.physics
        graphics = snapshot.graphics
        line = {
            "envelope": json.loads(message.model_dump_json()),
            "raw": {
                "speedKmh": physics.speed_kmh,
                "rpms": physics.rpms,
                "gear": physics.gear,
                "gas": physics.gas,
                "brake": physics.brake,
                "steerAngle": physics.steer_angle,
                "completedLaps": graphics.completed_laps,
                "normalizedCarPosition": graphics.normalized_position,
                "physicsPacketId": physics.packet_id,
                "graphicsPacketId": graphics.packet_id,
                "physicsStale": physics.stale,
                "graphicsStale": graphics.stale,
            },
        }
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(line, separators=(",", ":")) + "\n")
