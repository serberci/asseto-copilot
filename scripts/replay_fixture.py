"""Send a synthetic session to a running AI host.

`--pro` sends the bundled McLaren user lap so the host can compare it with the pro file.
"""

import json
import os
import sys
import urllib.request
from pathlib import Path

from coach_backend.references import ReferenceLibrary
from telemetry_schema import reference_session

ROOT = Path(__file__).resolve().parents[1]


def _jsonl(pro: bool) -> str:
    if not pro:
        return (ROOT / "fixtures" / "synthetic-session.jsonl").read_text(encoding="utf-8")
    lap = ReferenceLibrary().get("synthetic-user-spa-720s")
    if lap is None:
        raise SystemExit("The synthetic McLaren lap is not in the reference pack.")
    messages = reference_session(
        game=lap.game,
        track_id=lap.track_id,
        car_model=lap.car_model,
        lap_time_ms=lap.lap_time_ms,
        samples=[sample.model_dump() for sample in lap.samples],
    )
    return "\n".join(item.model_dump_json() for item in messages)


def main() -> None:
    token = os.environ.get("COACH_AUTH_TOKEN")
    if not token:
        raise SystemExit("Set COACH_AUTH_TOKEN to the token printed by the AI host.")
    base = os.environ.get("COACH_BACKEND_URL", "http://127.0.0.1:8080").rstrip("/")
    payload = json.dumps({"jsonl": _jsonl("--pro" in sys.argv)}).encode()
    request = urllib.request.Request(
        f"{base}/api/v1/replay",
        data=payload,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request) as response:
        print(response.read().decode())


if __name__ == "__main__":
    main()
