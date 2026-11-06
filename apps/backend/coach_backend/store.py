"""Sessions, laps, and telemetry archives."""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
from telemetry_schema.messages import Message, TelemetryMessage
from telemetry_schema.models import gear_label

from coach_backend.assembler import LapAssembler
from coach_backend.coaching import Scheduler, build_report
from coach_backend.copilot import ask
from coach_backend.tracks import TrackLibrary

PARQUET_SCHEMA = pa.schema(
    [
        ("timestamp", pa.string()),
        ("sequence", pa.int64()),
        ("normalized_progress", pa.float64()),
        ("elapsed_s", pa.float64()),
        ("speed_mps", pa.float64()),
        ("rpm", pa.int32()),
        ("gear_raw", pa.int32()),
        ("throttle", pa.float64()),
        ("brake", pa.float64()),
        ("clutch", pa.float64()),
        ("steering", pa.float64()),
        ("payload_json", pa.string()),
    ]
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Store:
    def __init__(self, data_dir: Path, model=None) -> None:
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.tracks = TrackLibrary(data_dir)
        self.model = model
        self.scheduler = Scheduler()
        self._lock = threading.Lock()
        self._connection = sqlite3.connect(self.data_dir / "coach.sqlite", check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._agents: dict[str, str] = {}
        self._keys: dict[str, tuple] = {}
        self._assemblers: dict[str, LapAssembler] = {}
        self.live: dict = {"session_id": None, "telemetry": None, "connected_agents": set()}
        self._create()

    def close(self) -> None:
        self._connection.close()

    def ingest(self, message: Message) -> dict:
        with self._lock:
            self.live["connected_agents"].add(message.agent_id)
            if message.type != "telemetry":
                return self._ack(message, self._agents.get(message.agent_id))
            session_id = self._session_for(message)
            self._append_jsonl(session_id, message)
            finished = self._assemblers[session_id].add(message)
            self.live["session_id"] = session_id
            self.live["telemetry"] = _public_sample(message)
            completed = None
            if finished is not None:
                completed = finished.lap_number
                self._save_lap(session_id, finished)
            self._maybe_speak(session_id, message)
            return self._ack(message, session_id, completed)

    def replay_jsonl(self, text: str) -> str | None:
        from telemetry_schema import parse_envelope

        last = None
        for line in text.splitlines():
            if not line.strip():
                continue
            ack = self.ingest(parse_envelope(json.loads(line)))
            last = ack.get("session_id") or last
        return last

    def sessions(self) -> list[dict]:
        rows = self._connection.execute("SELECT * FROM sessions ORDER BY started_at").fetchall()
        return [_session(row) for row in rows]

    def session(self, session_id: str) -> dict | None:
        row = self._connection.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
        return None if row is None else _session(row)

    def laps(self, session_id: str) -> list[dict]:
        rows = self._connection.execute(
            "SELECT * FROM laps WHERE session_id = ? ORDER BY lap_number",
            (session_id,),
        ).fetchall()
        return [_lap(row) for row in rows]

    def coaching(self, session_id: str) -> list[dict]:
        rows = self._connection.execute(
            "SELECT * FROM coaching_events WHERE session_id = ? ORDER BY created_at",
            (session_id,),
        ).fetchall()
        return [_event(row) for row in rows]

    def set_reference(self, session_id: str, lap_id: str) -> dict | None:
        lap = self._connection.execute(
            "SELECT * FROM laps WHERE id = ? AND session_id = ? AND valid = 1",
            (lap_id, session_id),
        ).fetchone()
        if lap is None:
            return None
        self._connection.execute("UPDATE sessions SET reference_lap_id = ? WHERE id = ?", (lap_id, session_id))
        self._connection.commit()
        return self.session(session_id)

    def analysis(self, lap_id: str) -> dict | None:
        lap = self._connection.execute("SELECT * FROM laps WHERE id = ?", (lap_id,)).fetchone()
        if lap is None:
            return None
        reference = self._reference_row(lap["session_id"], exclude=lap_id)
        if reference is None or not lap["parquet_path"] or not reference["parquet_path"]:
            return {"lap_id": lap_id, "reference_lap_id": None, "report": None}
        report = build_report(read_parquet(Path(lap["parquet_path"])), read_parquet(Path(reference["parquet_path"])), self._track(lap["session_id"]))
        return {
            "lap_id": lap_id,
            "reference_lap_id": reference["id"],
            "report": _public_report(report),
        }

    def context(self, session_id: str | None) -> dict:
        if session_id is None:
            session_id = self.live.get("session_id")
        session = self.session(session_id) if session_id else None
        if session is None:
            return {"available": False}
        lap_rows = self.laps(session_id)
        valid = [lap for lap in lap_rows if lap["valid"]]
        best = min(valid, key=lambda lap: lap["lap_time_ms"] or 10**12) if valid else None
        latest = valid[-1] if valid else None
        delta: dict = {"available": False, "reason": "no_reference_lap"}
        if latest and best and latest["id"] != best["id"]:
            analysed = self.analysis(latest["id"])
            report = analysed["report"] if analysed else None
            corner = report["corners"][0] if report and report["corners"] else {}
            loss = None if report is None else report["time_loss_s"]
            delta = {
                "available": report is not None and loss is not None,
                "time_loss_s": loss,
                "corner_id": corner.get("corner_id"),
                "corner_name": corner.get("name"),
                "reference_lap_time_s": None if best["lap_time_ms"] is None else round(best["lap_time_ms"] / 1000, 3),
                "latest_lap_time_s": None if latest["lap_time_ms"] is None else round(latest["lap_time_ms"] / 1000, 3),
            }
        return {
            "available": True,
            "current_session": {
                "id": session["id"],
                "track_id": session["track_id"],
                "car_model": session["car_model"],
                "player_nick": session["player_nick"],
            },
            "current_lap": {
                "available": latest is not None,
                "lap_number": None if latest is None else latest["lap_number"],
                "lap_time_s": None if latest is None or latest["lap_time_ms"] is None else round(latest["lap_time_ms"] / 1000, 3),
            },
            "lap_delta": delta,
            "best_lap": {
                "available": best is not None,
                "lap_number": None if best is None else best["lap_number"],
                "lap_time_s": None if best is None or best["lap_time_ms"] is None else round(best["lap_time_ms"] / 1000, 3),
            },
            "recent_coaching": self.coaching(session_id)[-8:],
        }

    def ask(self, question: str, session_id: str | None) -> dict:
        with self._lock:
            context = self.context(session_id)
            answer = ask(question, context, self.model)
            self._connection.execute(
                "INSERT INTO conversation_messages (id, session_id, role, text, created_at, evidence_json) VALUES (?, ?, ?, ?, ?, ?)",
                (str(uuid.uuid4()), context.get("current_session", {}).get("id") if context.get("available") else session_id, "user", question, _now(), "{}"),
            )
            self._connection.execute(
                "INSERT INTO conversation_messages (id, session_id, role, text, created_at, evidence_json) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    str(uuid.uuid4()),
                    context.get("current_session", {}).get("id") if context.get("available") else session_id,
                    "assistant",
                    answer["spoken_response"],
                    _now(),
                    json.dumps(answer["evidence"], default=str),
                ),
            )
            self._connection.commit()
            return answer

    def live_view(self) -> dict:
        session = self.session(self.live["session_id"]) if self.live.get("session_id") else None
        laps = self.laps(session["id"]) if session else []
        coaching = self.coaching(session["id"]) if session else []
        return {
            "connected_agents": len(self.live["connected_agents"]),
            "session": session,
            "telemetry": self.live.get("telemetry"),
            "laps": laps,
            "coaching": coaching,
        }

    def _session_for(self, message: TelemetryMessage) -> str:
        payload = message.payload
        key = (payload.track_id, payload.track_configuration, payload.car_model, payload.session_type)
        current = self._agents.get(message.agent_id)
        if current is not None and self._keys.get(message.agent_id) == key:
            return current
        session_id = str(uuid.uuid4())
        self._connection.execute(
            """INSERT INTO sessions
               (id, agent_id, game, track_id, track_configuration, car_model, car_skin, player_nick, session_type, started_at, reference_lap_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)""",
            (
                session_id,
                message.agent_id,
                message.game,
                payload.track_id,
                payload.track_configuration,
                payload.car_model,
                payload.car_skin,
                payload.player_nick,
                payload.session_type,
                message.timestamp.isoformat(),
            ),
        )
        self._connection.commit()
        self._agents[message.agent_id] = session_id
        self._keys[message.agent_id] = key
        self._assemblers[session_id] = LapAssembler()
        return session_id

    def _save_lap(self, session_id: str, lap) -> None:
        lap_id = str(uuid.uuid4())
        path = None
        if lap.samples:
            day = lap.started_at.date().isoformat()
            path = self.data_dir / "telemetry" / f"date={day}" / f"session={session_id}" / f"lap={lap.lap_number}.parquet"
            write_parquet(path, lap.samples)
        self._connection.execute(
            """INSERT INTO laps
               (id, session_id, lap_number, lap_time_ms, valid, invalid_reasons, started_at, ended_at, sample_count, parquet_path)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                lap_id,
                session_id,
                lap.lap_number,
                lap.lap_time_ms,
                1 if lap.valid else 0,
                json.dumps(lap.invalid_reasons),
                lap.started_at.isoformat(),
                lap.ended_at.isoformat(),
                len(lap.samples),
                None if path is None else str(path),
            ),
        )
        self._connection.commit()
        if not lap.valid or path is None:
            return
        reference = self._reference_row(session_id, exclude=lap_id)
        if reference is None or not reference["parquet_path"]:
            return
        report = build_report(read_parquet(path), read_parquet(Path(reference["parquet_path"])), self._track(session_id))
        for event in report["events"]:
            self._insert_event(session_id, lap_id, event)
            self.scheduler.push(event)

    def _maybe_speak(self, session_id: str, message: TelemetryMessage) -> None:
        payload = message.payload
        track = self._track(session_id)
        corners = [] if track is None else list(track.corners)
        spoken = self.scheduler.poll(
            brake=payload.brake,
            throttle=payload.throttle,
            progress=payload.normalized_progress,
            now=message.timestamp.timestamp(),
            corners=corners,
        )
        if spoken is None:
            return
        self._connection.execute(
            "UPDATE coaching_events SET delivered_at = ? WHERE session_id = ? AND dedup_key = ? AND delivered_at IS NULL",
            (message.timestamp.isoformat(), session_id, spoken.dedup_key),
        )
        self._connection.commit()

    def _insert_event(self, session_id: str, lap_id: str, event) -> None:
        self._connection.execute(
            """INSERT INTO coaching_events
               (id, session_id, lap_id, rule_id, corner_id, created_at, severity, priority, confidence, dedup_key,
                evidence_json, spoken_text, recommendation_allowed, time_impact_s, delivered_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)""",
            (
                str(uuid.uuid4()),
                session_id,
                lap_id,
                event.rule_id,
                event.corner_id,
                _now(),
                event.severity,
                event.priority,
                event.confidence,
                event.dedup_key,
                json.dumps({"evidence": event.evidence, "reference": event.reference, "advice": event.advice}),
                event.spoken_text,
                1 if event.recommendation_allowed else 0,
                event.time_impact_s,
            ),
        )
        self._connection.commit()

    def _reference_row(self, session_id: str, exclude: str):
        session = self._connection.execute("SELECT reference_lap_id FROM sessions WHERE id = ?", (session_id,)).fetchone()
        if session and session["reference_lap_id"] and session["reference_lap_id"] != exclude:
            chosen = self._connection.execute(
                "SELECT * FROM laps WHERE id = ? AND valid = 1",
                (session["reference_lap_id"],),
            ).fetchone()
            if chosen is not None:
                return chosen
        return self._connection.execute(
            """SELECT * FROM laps
               WHERE session_id = ? AND valid = 1 AND id != ? AND lap_time_ms IS NOT NULL
               ORDER BY lap_time_ms ASC LIMIT 1""",
            (session_id, exclude),
        ).fetchone()

    def _track(self, session_id: str):
        session = self.session(session_id)
        if session is None:
            return None
        return self.tracks.get(session["track_id"])

    def _append_jsonl(self, session_id: str, message: TelemetryMessage) -> None:
        path = self.data_dir / "sessions" / session_id / "telemetry.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(message.model_dump_json() + "\n")

    def _ack(self, message: Message, session_id: str | None, completed: int | None = None) -> dict:
        return {
            "type": "ack",
            "sequence": message.sequence,
            "session_id": session_id,
            "lap_completed": completed,
        }

    def _create(self) -> None:
        self._connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                agent_id TEXT NOT NULL,
                game TEXT NOT NULL,
                track_id TEXT NOT NULL,
                track_configuration TEXT NOT NULL,
                car_model TEXT NOT NULL,
                car_skin TEXT NOT NULL,
                player_nick TEXT NOT NULL,
                session_type TEXT NOT NULL,
                started_at TEXT NOT NULL,
                ended_at TEXT,
                reference_lap_id TEXT
            );
            CREATE TABLE IF NOT EXISTS laps (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                lap_number INTEGER NOT NULL,
                lap_time_ms INTEGER,
                valid INTEGER NOT NULL,
                invalid_reasons TEXT NOT NULL,
                started_at TEXT NOT NULL,
                ended_at TEXT,
                sample_count INTEGER NOT NULL,
                parquet_path TEXT
            );
            CREATE TABLE IF NOT EXISTS coaching_events (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                lap_id TEXT,
                rule_id TEXT NOT NULL,
                corner_id TEXT,
                created_at TEXT NOT NULL,
                severity TEXT NOT NULL,
                priority INTEGER NOT NULL,
                confidence REAL NOT NULL,
                dedup_key TEXT NOT NULL,
                evidence_json TEXT NOT NULL,
                spoken_text TEXT NOT NULL,
                recommendation_allowed INTEGER NOT NULL,
                time_impact_s REAL,
                delivered_at TEXT
            );
            CREATE TABLE IF NOT EXISTS conversation_messages (
                id TEXT PRIMARY KEY,
                session_id TEXT,
                role TEXT NOT NULL,
                text TEXT NOT NULL,
                created_at TEXT NOT NULL,
                evidence_json TEXT NOT NULL
            );
            """
        )
        self._connection.commit()


def write_parquet(path: Path, samples: list[TelemetryMessage]) -> None:
    start = samples[0].payload.physics_read_at
    rows = []
    for message in samples:
        payload = message.payload
        rows.append(
            {
                "timestamp": message.timestamp.isoformat(),
                "sequence": message.sequence,
                "normalized_progress": payload.normalized_progress,
                "elapsed_s": (payload.physics_read_at - start).total_seconds(),
                "speed_mps": payload.speed_mps,
                "rpm": payload.rpm,
                "gear_raw": payload.gear_raw,
                "throttle": payload.throttle,
                "brake": payload.brake,
                "clutch": payload.clutch,
                "steering": payload.steering,
                "payload_json": payload.model_dump_json(),
            }
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_pylist(rows, schema=PARQUET_SCHEMA), path)


def read_parquet(path: Path) -> list[dict]:
    return pq.read_table(path).to_pylist()


def _public_sample(message: TelemetryMessage) -> dict:
    payload = message.payload
    return {
        "speed_mps": payload.speed_mps,
        "rpm": payload.rpm,
        "gear_raw": payload.gear_raw,
        "gear": gear_label(payload.gear_raw),
        "throttle": payload.throttle,
        "brake": payload.brake,
        "clutch": payload.clutch,
        "steering": payload.steering,
        "normalized_progress": payload.normalized_progress,
        "lap_number": payload.lap_number,
        "completed_laps": payload.completed_laps,
        "current_lap_time_ms": payload.current_lap_time_ms,
        "last_lap_time_ms": payload.last_lap_time_ms,
        "best_lap_time_ms": payload.best_lap_time_ms,
        "track_id": payload.track_id,
        "car_model": payload.car_model,
        "player_nick": payload.player_nick,
        "session_status": payload.session_status,
        "session_type": payload.session_type,
        "in_pit": payload.in_pit,
        "physics_stale": payload.physics_stale,
        "graphics_stale": payload.graphics_stale,
    }


def _session(row: sqlite3.Row) -> dict:
    return {key: row[key] for key in row.keys()}


def _lap(row: sqlite3.Row) -> dict:
    data = {key: row[key] for key in row.keys()}
    data["valid"] = bool(data["valid"])
    data["invalid_reasons"] = json.loads(data["invalid_reasons"])
    return data


def _event(row: sqlite3.Row) -> dict:
    data = {key: row[key] for key in row.keys()}
    data["recommendation_allowed"] = bool(data["recommendation_allowed"])
    data["evidence"] = json.loads(data.pop("evidence_json"))
    return data


def _public_report(report: dict) -> dict:
    return {
        "delta": report["delta"],
        "corners": report["corners"],
        "time_loss_s": report["time_loss_s"],
        "events": [event.public() for event in report["events"]],
    }
