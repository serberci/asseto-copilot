"""Send the synthetic session to a running AI host."""

import json
import os
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    token = os.environ.get("COACH_AUTH_TOKEN")
    if not token:
        raise SystemExit("Set COACH_AUTH_TOKEN to the token printed by the AI host.")
    base = os.environ.get("COACH_BACKEND_URL", "http://127.0.0.1:8080").rstrip("/")
    payload = json.dumps({"jsonl": (ROOT / "fixtures" / "synthetic-session.jsonl").read_text(encoding="utf-8")}).encode()
    request = urllib.request.Request(
        f"{base}/api/v1/replay",
        data=payload,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request) as response:
        print(response.read().decode())


if __name__ == "__main__":
    main()
