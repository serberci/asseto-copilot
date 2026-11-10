"""Sessions, laps, and telemetry archives."""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import sqlite3
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
from telemetry_schema.messages import Message, TelemetryMessage
from telemetry_schema.models import gear_label

from coach_backend.assembler import LapAssembler
from coach_backend.coaching import Scheduler, build_report
from coach_backend.copilot import ask
from coach_backend.references import ReferenceLibrary, compare_pro, grip_flags
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


def _password_hash(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 200_000)
    return f"{salt.hex()}${digest.hex()}"


def _password_matches(password: str, stored: str | None) -> bool:
    if not stored or "$" not in stored:
        return False
    salt_hex, digest_hex = stored.split("$", 1)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), 200_000)
    return hmac.compare_digest(digest.hex(), digest_hex)


def _driver_caller(row: sqlite3.Row, *, from_agent_token: bool) -> Caller:
    is_admin = False if from_agent_token else row["role"] == "administrator"
    return Caller(is_admin=is_admin, driver_id=row["id"], display_name=row["display_name"])


@dataclass(frozen=True)
class Caller:
    """Who presented the token. The administrator is the host token, not a driver."""

    is_admin: bool
    driver_id: str | None
    display_name: str


ADMIN = Caller(is_admin=True, driver_id=None, display_name="administrator")
LAP_OWNER = "CASE WHEN laps.owner_locked = 1 THEN laps.owner_id ELSE sessions.driver_id END"


class Store:
    def __init__(self, data_dir: Path, model=None) -> None:
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.tracks = TrackLibrary(data_dir)
        self.references = ReferenceLibrary()
        self.model = model
        self.scheduler = Scheduler()
        self._lock = threading.Lock()
        self._connection = sqlite3.connect(self.data_dir / "coach.sqlite", check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._agents: dict[str, str] = {}
        self._keys: dict[str, tuple] = {}
        self._assemblers: dict[str, LapAssembler] = {}
        self.live: dict = {
            "session_id": None,
            "driver_id": None,
            "telemetry": None,
            "connected_agents": set(),
            "by_driver": {},
        }
        self._create()

    def close(self) -> None:
        self._connection.close()

    def ingest(self, message: Message, driver_id: str | None = None) -> dict:
        with self._lock:
            agent_key = (driver_id or "", message.agent_id)
            self.live["connected_agents"].add(agent_key)
            if message.type != "telemetry":
                return self._ack(message, self._agents.get(agent_key))
            session_id = self._session_for(message, driver_id)
            self._append_jsonl(session_id, message)
            finished = self._assemblers[session_id].add(message)
            sample = _public_sample(message)
            self.live["session_id"] = session_id
            self.live["driver_id"] = driver_id
            self.live["telemetry"] = sample
            self.live["by_driver"][driver_id or ""] = {"session_id": session_id, "telemetry": sample}
            completed = None
            if finished is not None:
                completed = finished.lap_number
                self._save_lap(session_id, finished)
            self._maybe_speak(session_id, message)
            return self._ack(message, session_id, completed)

    def replay_jsonl(self, text: str, driver_id: str | None = None) -> str | None:
        from telemetry_schema import parse_envelope

        last = None
        for line in text.splitlines():
            if not line.strip():
                continue
            ack = self.ingest(parse_envelope(json.loads(line)), driver_id)
            last = ack.get("session_id") or last
        return last

    def authenticate(self, token: str, admin_token: str) -> Caller | None:
        if token and admin_token and hmac.compare_digest(token, admin_token):
            return ADMIN
        if not token:
            return None
        digest = hashlib.sha256(token.encode()).hexdigest()
        row = self._connection.execute(
            "SELECT * FROM drivers WHERE token_hash = ? AND revoked = 0",
            (digest,),
        ).fetchone()
        if row is None:
            return None
        return _driver_caller(row, from_agent_token=True)

    def authenticate_session(self, session_id: str) -> Caller | None:
        row = self._connection.execute(
            """SELECT drivers.* FROM login_sessions
               JOIN drivers ON drivers.id = login_sessions.driver_id
               WHERE login_sessions.id = ? AND login_sessions.expires_at > ? AND drivers.revoked = 0""",
            (session_id, _now()),
        ).fetchone()
        if row is None:
            return None
        return _driver_caller(row, from_agent_token=False)

    def login(self, display_name: str, password: str) -> str | None:
        name = " ".join(display_name.split())
        row = self._connection.execute(
            "SELECT * FROM drivers WHERE display_name = ? AND revoked = 0",
            (name,),
        ).fetchone()
        if row is None or not _password_matches(password, row["password_hash"]):
            return None
        session_id = secrets.token_urlsafe(32)
        expires = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
        self._connection.execute(
            "INSERT INTO login_sessions (id, driver_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
            (session_id, row["id"], _now(), expires),
        )
        self._connection.commit()
        return session_id

    def logout(self, session_id: str) -> None:
        self._connection.execute("DELETE FROM login_sessions WHERE id = ?", (session_id,))
        self._connection.commit()

    def create_driver(self, display_name: str, password: str, role: str = "driver") -> dict:
        name = " ".join(display_name.split())
        if not name or len(name) > 40:
            raise ValueError("display name must be 1 to 40 characters")
        if len(password) < 8:
            raise ValueError("password must be at least 8 characters")
        if self._connection.execute("SELECT id FROM drivers WHERE display_name = ?", (name,)).fetchone() is not None:
            raise ValueError("That driver name is already used")
        driver_id = str(uuid.uuid4())
        placeholder = hashlib.sha256(secrets.token_urlsafe(32).encode()).hexdigest()
        self._connection.execute(
            """INSERT INTO drivers
               (id, display_name, token_hash, password_hash, role, created_at, revoked)
               VALUES (?, ?, ?, ?, ?, ?, 0)""",
            (driver_id, name, placeholder, _password_hash(password), role, _now()),
        )
        self._connection.commit()
        return {"id": driver_id, "display_name": name, "role": role}

    def issue_agent_token(self, driver_id: str) -> str | None:
        row = self._connection.execute(
            "SELECT id FROM drivers WHERE id = ? AND revoked = 0 AND role = 'driver'",
            (driver_id,),
        ).fetchone()
        if row is None:
            return None
        token = secrets.token_urlsafe(32)
        self._connection.execute(
            "UPDATE drivers SET token_hash = ? WHERE id = ?",
            (hashlib.sha256(token.encode()).hexdigest(), driver_id),
        )
        self._connection.commit()
        return token

    def list_drivers(self) -> list[dict]:
        rows = self._connection.execute(
            "SELECT id, display_name, created_at, revoked FROM drivers WHERE role = 'driver' ORDER BY created_at"
        ).fetchall()
        return [
            {
                "id": row["id"],
                "display_name": row["display_name"],
                "created_at": row["created_at"],
                "revoked": bool(row["revoked"]),
            }
            for row in rows
        ]

    def revoke_driver(self, driver_id: str) -> bool:
        cursor = self._connection.execute(
            "UPDATE drivers SET revoked = 1 WHERE id = ? AND revoked = 0 AND role = 'driver'",
            (driver_id,),
        )
        self._connection.execute("DELETE FROM login_sessions WHERE driver_id = ?", (driver_id,))
        self._connection.commit()
        return cursor.rowcount == 1

    def claim_unassigned(self, driver_id: str) -> int | None:
        driver = self._connection.execute(
            "SELECT id FROM drivers WHERE id = ? AND revoked = 0",
            (driver_id,),
        ).fetchone()
        if driver is None:
            return None
        cursor = self._connection.execute("UPDATE sessions SET driver_id = ? WHERE driver_id IS NULL", (driver_id,))
        self._connection.commit()
        return cursor.rowcount

    def delete_driver(self, driver_id: str) -> bool:
        row = self._connection.execute(
            "SELECT id FROM drivers WHERE id = ? AND role = 'driver'",
            (driver_id,),
        ).fetchone()
        if row is None:
            return False
        self._connection.execute("UPDATE sessions SET driver_id = NULL WHERE driver_id = ?", (driver_id,))
        self._connection.execute(
            "UPDATE laps SET owner_id = NULL, owner_locked = 1 WHERE owner_id = ?",
            (driver_id,),
        )
        self._connection.execute("DELETE FROM login_sessions WHERE driver_id = ?", (driver_id,))
        self._connection.execute("DELETE FROM drivers WHERE id = ?", (driver_id,))
        self._connection.commit()
        return True

    def assign_lap(self, lap_id: str, driver_id: str | None) -> bool:
        lap = self._connection.execute("SELECT id FROM laps WHERE id = ?", (lap_id,)).fetchone()
        if lap is None:
            return False
        if driver_id is not None:
            driver = self._connection.execute(
                "SELECT id FROM drivers WHERE id = ? AND role = 'driver' AND revoked = 0",
                (driver_id,),
            ).fetchone()
            if driver is None:
                return False
        self._connection.execute(
            "UPDATE laps SET owner_id = ?, owner_locked = 1 WHERE id = ?",
            (driver_id, lap_id),
        )
        self._connection.commit()
        return True

    def lap_catalog(self, caller: Caller, track_id: str | None = None) -> list[dict]:
        sql = f"""SELECT laps.*, sessions.track_id, sessions.car_model, sessions.game,
                         {LAP_OWNER} AS effective_owner_id, drivers.display_name AS driver_name
                  FROM laps
                  JOIN sessions ON sessions.id = laps.session_id
                  LEFT JOIN drivers ON drivers.id = {LAP_OWNER}
                  WHERE 1 = 1"""
        params: list[str] = []
        if not caller.is_admin:
            sql += f" AND {LAP_OWNER} = ?"
            params.append(caller.driver_id or "")
        if track_id:
            sql += " AND sessions.track_id = ?"
            params.append(track_id)
        sql += " ORDER BY laps.started_at, laps.lap_number"
        return [_catalog_lap(row) for row in self._connection.execute(sql, params).fetchall()]

    def performance(self, caller: Caller, track_id: str) -> dict:
        rows = self._connection.execute(
            f"""SELECT laps.* FROM laps
               JOIN sessions ON sessions.id = laps.session_id
               WHERE {LAP_OWNER} = ? AND sessions.track_id = ?
                 AND laps.valid = 1 AND laps.lap_time_ms IS NOT NULL
               ORDER BY laps.started_at, laps.lap_number""",
            (caller.driver_id, track_id),
        ).fetchall()
        points = []
        previous: float | None = None
        for row in rows:
            seconds = round(row["lap_time_ms"] / 1000, 3)
            points.append(
                {
                    "lap_id": row["id"],
                    "lap_time_s": seconds,
                    "improvement_s": None if previous is None else round(previous - seconds, 3),
                    "started_at": row["started_at"],
                }
            )
            previous = seconds
        return {"track_id": track_id, "laps": points}

    def sessions(self, caller: Caller | None = None) -> list[dict]:
        caller = caller or ADMIN
        if caller.is_admin:
            rows = self._connection.execute("SELECT * FROM sessions ORDER BY started_at").fetchall()
        else:
            rows = self._connection.execute(
                "SELECT * FROM sessions WHERE driver_id = ? ORDER BY started_at",
                (caller.driver_id,),
            ).fetchall()
        return [_session(row) for row in rows]

    def session(self, session_id: str, caller: Caller | None = None) -> dict | None:
        caller = caller or ADMIN
        row = self._connection.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
        if row is None:
            return None
        if not caller.is_admin and row["driver_id"] != caller.driver_id:
            return None
        return _session(row)

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

    def set_reference(self, session_id: str, lap_id: str, caller: Caller | None = None) -> dict | None:
        caller = caller or ADMIN
        if self.session(session_id, caller) is None:
            return None
        lap = self._connection.execute(
            "SELECT * FROM laps WHERE id = ? AND session_id = ? AND valid = 1",
            (lap_id, session_id),
        ).fetchone()
        if lap is None:
            return None
        self._connection.execute("UPDATE sessions SET reference_lap_id = ? WHERE id = ?", (lap_id, session_id))
        self._connection.commit()
        return self.session(session_id, caller)

    def analysis(self, lap_id: str, caller: Caller | None = None) -> dict | None:
        caller = caller or ADMIN
        lap = self._visible_lap(lap_id, caller)
        if lap is None:
            return None
        reference = self._reference_row(lap["session_id"], exclude=lap_id, owner_id=self._owner_of(lap_id))
        if reference is None or not lap["parquet_path"] or not reference["parquet_path"]:
            return {"lap_id": lap_id, "reference_lap_id": None, "report": None}
        report = build_report(read_parquet(Path(lap["parquet_path"])), read_parquet(Path(reference["parquet_path"])), self._track(lap["session_id"]))
        return {
            "lap_id": lap_id,
            "reference_lap_id": reference["id"],
            "report": _public_report(report),
        }

    def benchmark(self, lap_id: str, caller: Caller | None = None) -> dict | None:
        caller = caller or ADMIN
        lap = self._visible_lap(lap_id, caller)
        if lap is None:
            return None
        session = self.session(lap["session_id"], ADMIN)
        if session is None:
            return None
        personal = self.analysis(lap_id, caller)
        report = None if personal is None else personal.get("report")
        rows = read_parquet(Path(lap["parquet_path"])) if lap["parquet_path"] else []
        payloads = [json.loads(row["payload_json"]) for row in rows if row.get("payload_json")]
        pro_lap = self.references.pro_for(session["game"], session["track_id"], session["car_model"])
        if pro_lap is None:
            pro = {
                "available": False,
                "reason": "no_pro_reference",
                "recommendation_allowed": False,
                "spoken_text": "No pro file matches this game, track, and car.",
                "tips": [],
            }
        else:
            pro = compare_pro(
                rows,
                pro_lap,
                game=session["game"],
                track_id=session["track_id"],
                car_model=session["car_model"],
                lap_time_ms=lap["lap_time_ms"],
            )
        return {
            "lap_id": lap_id,
            "personal": {
                "available": report is not None,
                "reference_lap_id": None if personal is None else personal.get("reference_lap_id"),
                "time_loss_s": None if report is None else report.get("time_loss_s"),
                "tips": [] if report is None else report.get("events") or [],
            },
            "others": self._others(lap, session),
            "pro": pro,
            "grip": grip_flags(payloads),
        }

    def context(self, session_id: str | None, caller: Caller | None = None) -> dict:
        caller = caller or ADMIN
        if session_id is None:
            session_id = self._live_session_id(caller)
        session = self.session(session_id, caller) if session_id else None
        if session is None:
            return {"available": False}
        lap_rows = self.laps(session_id)
        valid = [lap for lap in lap_rows if lap["valid"]]
        latest = valid[-1] if valid else None
        reference = self._reference_row(session_id, exclude=latest["id"]) if latest else None
        delta: dict = {"available": False, "reason": "no_reference_lap"}
        if latest and reference is not None:
            analysed = self.analysis(latest["id"])
            report = analysed["report"] if analysed else None
            corner = report["corners"][0] if report and report["corners"] else {}
            loss = None if report is None else report["time_loss_s"]
            delta = {
                "available": report is not None and loss is not None,
                "time_loss_s": loss,
                "corner_id": corner.get("corner_id"),
                "corner_name": corner.get("name"),
                "reference_lap_time_s": None if reference["lap_time_ms"] is None else round(reference["lap_time_ms"] / 1000, 3),
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
                "available": reference is not None,
                "lap_number": None if reference is None else reference["lap_number"],
                "lap_time_s": None
                if reference is None or reference["lap_time_ms"] is None
                else round(reference["lap_time_ms"] / 1000, 3),
            },
            "recent_coaching": self.coaching(session_id)[-8:],
        }

    def ask(self, question: str, session_id: str | None, caller: Caller | None = None) -> dict:
        caller = caller or ADMIN
        with self._lock:
            context = self.context(session_id, caller)
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

    def live_view(self, caller: Caller | None = None) -> dict:
        caller = caller or ADMIN
        session_id = self._live_session_id(caller)
        session = self.session(session_id, caller) if session_id else None
        laps = self.laps(session["id"]) if session else []
        coaching = self.coaching(session["id"]) if session else []
        if caller.is_admin:
            agent_count = len(self.live["connected_agents"])
            telemetry = self.live.get("telemetry") if session_id == self.live.get("session_id") else None
        else:
            agent_count = sum(1 for driver_id, _agent in self.live["connected_agents"] if driver_id == (caller.driver_id or ""))
            slot = self.live["by_driver"].get(caller.driver_id or "")
            telemetry = None if slot is None else slot.get("telemetry")
        return {
            "connected_agents": agent_count,
            "driver_id": None if session is None else session.get("driver_id"),
            "session": session,
            "telemetry": telemetry,
            "laps": laps,
            "coaching": coaching,
        }

    def _live_session_id(self, caller: Caller) -> str | None:
        if caller.is_admin:
            return self.live.get("session_id")
        slot = self.live["by_driver"].get(caller.driver_id or "")
        return None if slot is None else slot.get("session_id")

    def _visible_lap(self, lap_id: str, caller: Caller):
        lap = self._connection.execute("SELECT * FROM laps WHERE id = ?", (lap_id,)).fetchone()
        if lap is None:
            return None
        if not caller.is_admin and self._owner_of(lap_id) != caller.driver_id:
            return None
        return lap

    def _owner_of(self, lap_id: str) -> str | None:
        row = self._connection.execute(
            f"""SELECT {LAP_OWNER} AS owner_id FROM laps
                JOIN sessions ON sessions.id = laps.session_id
                WHERE laps.id = ?""",
            (lap_id,),
        ).fetchone()
        return None if row is None else row["owner_id"]

    def _others(self, lap, session: dict) -> dict:
        empty = {
            "available": False,
            "reason": "no_other_driver",
            "driver_id": None,
            "driver_name": None,
            "reference_lap_id": None,
            "time_loss_s": None,
            "tips": [],
            "board": [],
        }
        owner_id = self._owner_of(lap["id"])
        if owner_id is None:
            empty["reason"] = "no_driver"
            return empty
        if not lap["parquet_path"]:
            return empty
        rows = self._connection.execute(
            f"""SELECT laps.*, drivers.id AS driver_id, drivers.display_name AS driver_name
               FROM laps
               JOIN sessions ON sessions.id = laps.session_id
               JOIN drivers ON drivers.id = {LAP_OWNER}
               WHERE sessions.game = ? AND sessions.track_id = ? AND sessions.car_model = ?
                 AND {LAP_OWNER} != ?
                 AND laps.valid = 1 AND laps.lap_time_ms IS NOT NULL AND laps.parquet_path IS NOT NULL
               ORDER BY laps.lap_time_ms ASC""",
            (session["game"], session["track_id"], session["car_model"], owner_id),
        ).fetchall()
        board = []
        seen: set[str] = set()
        for row in rows:
            if row["driver_id"] in seen:
                continue
            seen.add(row["driver_id"])
            board.append(
                {
                    "driver_id": row["driver_id"],
                    "driver_name": row["driver_name"],
                    "lap_id": row["id"],
                    "lap_time_s": round(row["lap_time_ms"] / 1000, 3),
                }
            )
        if not board:
            empty["board"] = []
            return empty
        fastest = rows[0]
        report = build_report(
            read_parquet(Path(lap["parquet_path"])),
            read_parquet(Path(fastest["parquet_path"])),
            self._track(session["id"]),
        )
        public = _public_report(report)
        name = fastest["driver_name"]
        for tip in public["events"]:
            tip["spoken_text"] = f"Against {name}: {tip['spoken_text']}"
        return {
            "available": public["time_loss_s"] is not None,
            "reason": None,
            "driver_id": fastest["driver_id"],
            "driver_name": name,
            "reference_lap_id": fastest["id"],
            "time_loss_s": public["time_loss_s"],
            "tips": public["events"],
            "board": board,
        }

    def _session_for(self, message: TelemetryMessage, driver_id: str | None = None) -> str:
        payload = message.payload
        key = (driver_id, payload.track_id, payload.track_configuration, payload.car_model, payload.session_type)
        agent_key = (driver_id or "", message.agent_id)
        current = self._agents.get(agent_key)
        if current is not None and self._keys.get(agent_key) == key:
            return current
        session_id = str(uuid.uuid4())
        self._connection.execute(
            """INSERT INTO sessions
               (id, agent_id, driver_id, game, track_id, track_configuration, car_model, car_skin, player_nick, session_type, started_at, reference_lap_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)""",
            (
                session_id,
                message.agent_id,
                driver_id,
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
        self._agents[agent_key] = session_id
        self._keys[agent_key] = key
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

    def _reference_row(self, session_id: str, exclude: str, owner_id: str | None = None):
        session = self._connection.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
        if session is None:
            return None
        owner = session["driver_id"] if owner_id is None else owner_id
        if session["reference_lap_id"] and session["reference_lap_id"] != exclude:
            chosen = self._connection.execute(
                "SELECT * FROM laps WHERE id = ? AND valid = 1",
                (session["reference_lap_id"],),
            ).fetchone()
            if chosen is not None and self._owner_of(chosen["id"]) == owner:
                return chosen
        return self._connection.execute(
            f"""SELECT laps.* FROM laps
               JOIN sessions ON sessions.id = laps.session_id
               WHERE sessions.game = ? AND sessions.track_id = ? AND sessions.car_model = ?
                 AND {LAP_OWNER} IS ?
                 AND laps.valid = 1 AND laps.id != ? AND laps.lap_time_ms IS NOT NULL
               ORDER BY laps.lap_time_ms ASC LIMIT 1""",
            (session["game"], session["track_id"], session["car_model"], owner, exclude),
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
        self._connection.execute(
            """CREATE TABLE IF NOT EXISTS drivers (
                id TEXT PRIMARY KEY,
                display_name TEXT NOT NULL UNIQUE,
                token_hash TEXT NOT NULL UNIQUE,
                password_hash TEXT,
                role TEXT NOT NULL DEFAULT 'driver',
                created_at TEXT NOT NULL,
                revoked INTEGER NOT NULL DEFAULT 0
            )"""
        )
        self._connection.execute(
            """CREATE TABLE IF NOT EXISTS login_sessions (
                id TEXT PRIMARY KEY,
                driver_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL
            )"""
        )
        columns = {row[1] for row in self._connection.execute("PRAGMA table_info(sessions)")}
        if "driver_id" not in columns:
            self._connection.execute("ALTER TABLE sessions ADD COLUMN driver_id TEXT")
        lap_columns = {row[1] for row in self._connection.execute("PRAGMA table_info(laps)")}
        if "owner_id" not in lap_columns:
            self._connection.execute("ALTER TABLE laps ADD COLUMN owner_id TEXT")
        if "owner_locked" not in lap_columns:
            self._connection.execute("ALTER TABLE laps ADD COLUMN owner_locked INTEGER NOT NULL DEFAULT 0")
        driver_columns = {row[1] for row in self._connection.execute("PRAGMA table_info(drivers)")}
        if "password_hash" not in driver_columns:
            self._connection.execute("ALTER TABLE drivers ADD COLUMN password_hash TEXT")
        if "role" not in driver_columns:
            self._connection.execute("ALTER TABLE drivers ADD COLUMN role TEXT NOT NULL DEFAULT 'driver'")
        self._connection.commit()
        self._ensure_administrator()

    def _ensure_administrator(self) -> None:
        row = self._connection.execute("SELECT * FROM drivers WHERE role = 'administrator'").fetchone()
        if row is not None and row["password_hash"]:
            return
        password = secrets.token_urlsafe(18)
        if row is None:
            self.create_driver("administrator", password, role="administrator")
        else:
            self._connection.execute(
                "UPDATE drivers SET password_hash = ? WHERE id = ?",
                (_password_hash(password), row["id"]),
            )
            self._connection.commit()
        path = self.data_dir / "admin.password"
        path.write_text(password + "\n", encoding="utf-8")
        print(f"Administrator password written to {path}")


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


def _catalog_lap(row: sqlite3.Row) -> dict:
    lap = _lap(row)
    return {
        "id": lap["id"],
        "session_id": lap["session_id"],
        "lap_number": lap["lap_number"],
        "lap_time_ms": lap["lap_time_ms"],
        "valid": lap["valid"],
        "invalid_reasons": lap["invalid_reasons"],
        "started_at": lap["started_at"],
        "track_id": row["track_id"],
        "car_model": row["car_model"],
        "game": row["game"],
        "driver_id": row["effective_owner_id"],
        "driver_name": row["driver_name"],
    }


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
