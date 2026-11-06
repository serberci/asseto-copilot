"""Process settings for the AI host. Secrets stay in the data directory or the environment."""

from __future__ import annotations

import os
import secrets
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Settings:
    data_dir: Path
    auth_token: str
    ollama_host: str | None
    ollama_model: str
    static_dir: Path | None
    host: str = "0.0.0.0"
    port: int = 8080

    @classmethod
    def from_env(cls) -> Settings:
        data_dir = Path(os.environ.get("COACH_DATA_DIR", "data")).resolve()
        data_dir.mkdir(parents=True, exist_ok=True)
        token = os.environ.get("COACH_AUTH_TOKEN") or _load_token(data_dir)
        static_path = _static_dir()
        return cls(
            data_dir=data_dir,
            auth_token=token,
            ollama_host=os.environ.get("COACH_OLLAMA_HOST") or None,
            ollama_model=os.environ.get("COACH_OLLAMA_MODEL", "llama3.2:3b"),
            static_dir=static_path,
            host=os.environ.get("COACH_HOST", "0.0.0.0"),
            port=int(os.environ.get("COACH_PORT", "8080")),
        )

    def language_model(self):
        if not self.ollama_host:
            return None
        import httpx

        from coach_backend.copilot import OllamaModel

        return OllamaModel(self.ollama_host, self.ollama_model, httpx.Client())

    def transcriber(self):
        return None

    def synthesizer(self):
        return None


def _static_dir() -> Path | None:
    chosen = os.environ.get("COACH_STATIC_DIR")
    if chosen:
        return Path(chosen)
    candidate = Path.cwd() / "apps" / "frontend" / "dist"
    if (candidate / "index.html").exists():
        return candidate
    return None


def _load_token(data_dir: Path) -> str:
    path = data_dir / "auth.token"
    if path.exists():
        return path.read_text(encoding="utf-8").strip()
    token = secrets.token_urlsafe(24)
    path.write_text(token + "\n", encoding="utf-8")
    print(f"Created API token at {path}")
    return token
