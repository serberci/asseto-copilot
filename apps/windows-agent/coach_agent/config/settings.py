"""Per-user agent settings. The backend address is configuration, not code."""

from __future__ import annotations

import json
import os
import sys
import uuid
from pathlib import Path

from pydantic import BaseModel, Field


def app_data_dir() -> Path:
    override = os.environ.get("COACH_AGENT_HOME")
    if override:
        return Path(override)
    if sys.platform == "win32":
        root = os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming"))
        return Path(root) / "AssettoCorsaCoachAgent"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "AssettoCorsaCoachAgent"
    return Path.home() / ".local" / "share" / "assetto-corsa-coach-agent"


class AgentSettings(BaseModel):
    backend_url: str = "ws://127.0.0.1:8080/ws/telemetry"
    auth_token: str = ""
    agent_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    physics_hz: float = 100
    graphics_hz: float = 60
    publish_hz: float = 20
    heartbeat_s: float = 1
    log_level: str = "INFO"
    launch_at_login: bool = False
    start_minimized: bool = False
    push_to_talk_key: str = "V"
    input_device: str | None = None
    output_device: str | None = None
    record_jsonl: bool = True

    @classmethod
    def load(cls, directory: Path | None = None) -> AgentSettings:
        path = (directory or app_data_dir()) / "settings.json"
        if not path.exists():
            settings = cls()
            settings.save(directory)
            return settings
        return cls.model_validate(json.loads(path.read_text(encoding="utf-8")))

    def save(self, directory: Path | None = None) -> Path:
        root = directory or app_data_dir()
        root.mkdir(parents=True, exist_ok=True)
        path = root / "settings.json"
        path.write_text(self.model_dump_json(indent=2), encoding="utf-8")
        return path
