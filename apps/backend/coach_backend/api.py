"""HTTP and WebSocket boundaries."""

from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from telemetry_schema import SchemaError, parse_envelope

from coach_backend.copilot import answer_audio
from coach_backend.settings import Settings
from coach_backend.store import Store


class ReferenceBody(BaseModel):
    lap_id: str = Field(min_length=1)


class AskBody(BaseModel):
    question: str = Field(min_length=1, max_length=500)
    session_id: str | None = None


class ReplayBody(BaseModel):
    jsonl: str = Field(min_length=1)


class Hub:
    def __init__(self) -> None:
        self._queues: list[asyncio.Queue] = []

    def subscribe(self) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=8)
        self._queues.append(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        if queue in self._queues:
            self._queues.remove(queue)

    def publish(self, snapshot: dict) -> None:
        for queue in self._queues:
            if queue.full():
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            queue.put_nowait(snapshot)


def create_app(settings: Settings | None = None, store: Store | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    store = store or Store(settings.data_dir, model=settings.language_model())
    app = FastAPI(title="Assetto Corsa Coach", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.state.settings = settings
    app.state.store = store
    app.state.hub = Hub()

    @app.get("/api/v1/health")
    def health() -> dict:
        return {"status": "ok", "version": "0.1.0"}

    @app.get("/api/v1/live")
    def live(request: Request) -> dict:
        _authorize(request)
        return request.app.state.store.live_view()

    @app.get("/api/v1/sessions")
    def sessions(request: Request) -> dict:
        _authorize(request)
        return {"sessions": request.app.state.store.sessions()}

    @app.get("/api/v1/sessions/{session_id}")
    def session_detail(session_id: str, request: Request) -> dict:
        _authorize(request)
        session = request.app.state.store.session(session_id)
        if session is None:
            raise HTTPException(404, "session not found")
        return session

    @app.get("/api/v1/sessions/{session_id}/laps")
    def session_laps(session_id: str, request: Request) -> dict:
        _authorize(request)
        if request.app.state.store.session(session_id) is None:
            raise HTTPException(404, "session not found")
        return {"laps": request.app.state.store.laps(session_id)}

    @app.get("/api/v1/sessions/{session_id}/coaching")
    def session_coaching(session_id: str, request: Request) -> dict:
        _authorize(request)
        return {"coaching": request.app.state.store.coaching(session_id)}

    @app.post("/api/v1/sessions/{session_id}/reference")
    def set_reference(session_id: str, body: ReferenceBody, request: Request) -> dict:
        _authorize(request)
        updated = request.app.state.store.set_reference(session_id, body.lap_id)
        if updated is None:
            raise HTTPException(404, "valid lap not found in this session")
        return updated

    @app.get("/api/v1/laps/{lap_id}/analysis")
    def lap_analysis(lap_id: str, request: Request) -> dict:
        _authorize(request)
        report = request.app.state.store.analysis(lap_id)
        if report is None:
            raise HTTPException(404, "lap not found")
        return report

    @app.get("/api/v1/laps/{lap_id}/benchmark")
    def lap_benchmark(lap_id: str, request: Request) -> dict:
        _authorize(request)
        report = request.app.state.store.benchmark(lap_id)
        if report is None:
            raise HTTPException(404, "lap not found")
        return report

    @app.get("/api/v1/references")
    def references(request: Request) -> dict:
        _authorize(request)
        return {"references": request.app.state.store.references.list_laps()}

    @app.get("/api/v1/tracks")
    def tracks(request: Request) -> dict:
        _authorize(request)
        return {"tracks": request.app.state.store.tracks.list_tracks()}

    @app.post("/api/v1/copilot/ask")
    def copilot_ask(body: AskBody, request: Request) -> dict:
        _authorize(request)
        return request.app.state.store.ask(body.question, body.session_id)

    @app.post("/api/v1/replay")
    def replay(body: ReplayBody, request: Request) -> dict:
        _authorize(request)
        try:
            session_id = request.app.state.store.replay_jsonl(body.jsonl)
        except SchemaError as exc:
            raise HTTPException(422, str(exc)) from exc
        return {"session_id": session_id}

    @app.websocket("/ws/telemetry")
    async def telemetry(websocket: WebSocket) -> None:
        if not _token_ok(websocket, websocket.app.state.settings.auth_token):
            await websocket.close(code=1008)
            return
        await websocket.accept()
        store_ = websocket.app.state.store
        hub: Hub = websocket.app.state.hub
        try:
            while True:
                raw = await websocket.receive_json()
                try:
                    message = parse_envelope(raw)
                except SchemaError as exc:
                    await websocket.send_json({"type": "error", "detail": str(exc)})
                    continue
                ack = store_.ingest(message)
                hub.publish(store_.live_view())
                await websocket.send_json(ack)
        except WebSocketDisconnect:
            return

    @app.websocket("/ws/dashboard")
    async def dashboard(websocket: WebSocket) -> None:
        if not _token_ok(websocket, websocket.app.state.settings.auth_token):
            await websocket.close(code=1008)
            return
        await websocket.accept()
        hub: Hub = websocket.app.state.hub
        queue = hub.subscribe()
        await websocket.send_json({"type": "snapshot", **websocket.app.state.store.live_view()})
        try:
            while True:
                snapshot = await queue.get()
                await websocket.send_json({"type": "snapshot", **snapshot})
        except WebSocketDisconnect:
            hub.unsubscribe(queue)

    @app.websocket("/ws/audio")
    async def audio(websocket: WebSocket) -> None:
        if not _token_ok(websocket, websocket.app.state.settings.auth_token):
            await websocket.close(code=1008)
            return
        await websocket.accept()
        try:
            while True:
                payload = await websocket.receive_json()
                clip = bytes.fromhex(payload.get("pcm_hex") or "")
                result = answer_audio(
                    clip,
                    int(payload.get("sample_rate") or 16000),
                    lambda question: websocket.app.state.store.ask(question, payload.get("session_id")),
                    websocket.app.state.settings.transcriber(),
                    websocket.app.state.settings.synthesizer(),
                )
                await websocket.send_json(result)
        except WebSocketDisconnect:
            return

    static_dir = settings.static_dir
    if static_dir and static_dir.exists():
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="dashboard")
    return app


def _authorize(request: Request) -> None:
    if not _header_or_query(request.headers.get("authorization"), request.query_params.get("token"), request.app.state.settings.auth_token):
        raise HTTPException(status_code=401, detail="unauthorized")


def _token_ok(websocket: WebSocket, expected: str) -> bool:
    return _header_or_query(websocket.headers.get("authorization"), websocket.query_params.get("token"), expected)


def _header_or_query(header: str | None, query: str | None, expected: str) -> bool:
    if not expected:
        return False
    if header == f"Bearer {expected}":
        return True
    return query == expected


def index_file(static_dir: Path | None) -> FileResponse | None:
    if static_dir is None:
        return None
    path = static_dir / "index.html"
    if not path.exists():
        return None
    return FileResponse(path)
