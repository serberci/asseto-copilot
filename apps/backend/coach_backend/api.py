"""HTTP and WebSocket boundaries."""

from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from telemetry_schema import SchemaError, parse_envelope

from coach_backend.copilot import answer_audio
from coach_backend.settings import Settings
from coach_backend.store import Caller, Store


class ReferenceBody(BaseModel):
    lap_id: str = Field(min_length=1)


class AskBody(BaseModel):
    question: str = Field(min_length=1, max_length=500)
    session_id: str | None = None


class ReplayBody(BaseModel):
    jsonl: str = Field(min_length=1)


class DriverBody(BaseModel):
    display_name: str = Field(min_length=1, max_length=40)
    password: str = Field(min_length=8, max_length=200)


class AssignLapBody(BaseModel):
    driver_id: str | None = None


class LoginBody(BaseModel):
    display_name: str = Field(min_length=1, max_length=40)
    password: str = Field(min_length=1, max_length=200)


SESSION_COOKIE = "coach_session"


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

    @app.post("/api/v1/login")
    def login(body: LoginBody, request: Request, response: Response) -> dict:
        session_id = request.app.state.store.login(body.display_name, body.password)
        if session_id is None:
            raise HTTPException(status_code=401, detail="The name or password is wrong")
        response.set_cookie(SESSION_COOKIE, session_id, httponly=True, samesite="lax", path="/", max_age=60 * 60 * 24 * 30)
        caller = request.app.state.store.authenticate_session(session_id)
        return _public_caller(caller) if caller is not None else {}

    @app.post("/api/v1/logout")
    def logout(request: Request, response: Response) -> dict:
        session_id = request.cookies.get(SESSION_COOKIE)
        if session_id:
            request.app.state.store.logout(session_id)
        response.delete_cookie(SESSION_COOKIE, path="/")
        return {"ok": True}

    @app.get("/api/v1/me")
    def me(request: Request) -> dict:
        return _public_caller(_caller(request))

    @app.post("/api/v1/agent-token")
    def agent_token(request: Request) -> dict:
        caller = _caller(request)
        if caller.is_admin or not caller.driver_id:
            raise HTTPException(status_code=403, detail="A driver generates their own agent token")
        token = request.app.state.store.issue_agent_token(caller.driver_id)
        if token is None:
            raise HTTPException(status_code=404, detail="driver not found")
        return {"token": token}

    @app.get("/api/v1/drivers")
    def drivers(request: Request) -> dict:
        _require_admin(request)
        return {"drivers": request.app.state.store.list_drivers()}

    @app.post("/api/v1/drivers", status_code=201)
    def create_driver(body: DriverBody, request: Request) -> dict:
        _require_admin(request)
        try:
            return request.app.state.store.create_driver(body.display_name, body.password)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    @app.post("/api/v1/drivers/{driver_id}/revoke")
    def revoke_driver(driver_id: str, request: Request) -> dict:
        _require_admin(request)
        if not request.app.state.store.revoke_driver(driver_id):
            raise HTTPException(404, "driver not found")
        return {"id": driver_id, "revoked": True}

    @app.post("/api/v1/drivers/{driver_id}/claim-unassigned")
    def claim_unassigned(driver_id: str, request: Request) -> dict:
        _require_admin(request)
        count = request.app.state.store.claim_unassigned(driver_id)
        if count is None:
            raise HTTPException(404, "driver not found")
        return {"id": driver_id, "sessions": count}

    @app.delete("/api/v1/drivers/{driver_id}")
    def delete_driver(driver_id: str, request: Request) -> dict:
        _require_admin(request)
        if not request.app.state.store.delete_driver(driver_id):
            raise HTTPException(404, "driver not found")
        return {"id": driver_id, "deleted": True}

    @app.post("/api/v1/laps/{lap_id}/assign")
    def assign_lap(lap_id: str, body: AssignLapBody, request: Request) -> dict:
        _require_admin(request)
        if not request.app.state.store.assign_lap(lap_id, body.driver_id):
            raise HTTPException(404, "lap or driver not found")
        return {"id": lap_id, "driver_id": body.driver_id}

    @app.get("/api/v1/laps")
    def lap_catalog(request: Request, track_id: str | None = None) -> dict:
        return {"laps": request.app.state.store.lap_catalog(_caller(request), track_id)}

    @app.get("/api/v1/performance")
    def performance(request: Request, track_id: str) -> dict:
        return request.app.state.store.performance(_caller(request), track_id)

    @app.get("/api/v1/live")
    def live(request: Request) -> dict:
        return request.app.state.store.live_view(_caller(request))

    @app.get("/api/v1/sessions")
    def sessions(request: Request) -> dict:
        return {"sessions": request.app.state.store.sessions(_caller(request))}

    @app.get("/api/v1/sessions/{session_id}")
    def session_detail(session_id: str, request: Request) -> dict:
        session = request.app.state.store.session(session_id, _caller(request))
        if session is None:
            raise HTTPException(404, "session not found")
        return session

    @app.get("/api/v1/sessions/{session_id}/laps")
    def session_laps(session_id: str, request: Request) -> dict:
        if request.app.state.store.session(session_id, _caller(request)) is None:
            raise HTTPException(404, "session not found")
        return {"laps": request.app.state.store.laps(session_id)}

    @app.get("/api/v1/sessions/{session_id}/coaching")
    def session_coaching(session_id: str, request: Request) -> dict:
        if request.app.state.store.session(session_id, _caller(request)) is None:
            raise HTTPException(404, "session not found")
        return {"coaching": request.app.state.store.coaching(session_id)}

    @app.post("/api/v1/sessions/{session_id}/reference")
    def set_reference(session_id: str, body: ReferenceBody, request: Request) -> dict:
        updated = request.app.state.store.set_reference(session_id, body.lap_id, _caller(request))
        if updated is None:
            raise HTTPException(404, "valid lap not found in this session")
        return updated

    @app.get("/api/v1/laps/{lap_id}/analysis")
    def lap_analysis(lap_id: str, request: Request) -> dict:
        report = request.app.state.store.analysis(lap_id, _caller(request))
        if report is None:
            raise HTTPException(404, "lap not found")
        return report

    @app.get("/api/v1/laps/{lap_id}/benchmark")
    def lap_benchmark(lap_id: str, request: Request) -> dict:
        report = request.app.state.store.benchmark(lap_id, _caller(request))
        if report is None:
            raise HTTPException(404, "lap not found")
        return report

    @app.get("/api/v1/references")
    def references(request: Request) -> dict:
        _caller(request)
        return {"references": request.app.state.store.references.list_laps()}

    @app.get("/api/v1/tracks")
    def tracks(request: Request) -> dict:
        _caller(request)
        return {"tracks": request.app.state.store.tracks.list_tracks()}

    @app.post("/api/v1/copilot/ask")
    def copilot_ask(body: AskBody, request: Request) -> dict:
        caller = _caller(request)
        return request.app.state.store.ask(body.question, body.session_id, caller)

    @app.post("/api/v1/replay")
    def replay(body: ReplayBody, request: Request) -> dict:
        caller = _caller(request)
        try:
            session_id = request.app.state.store.replay_jsonl(body.jsonl, caller.driver_id)
        except SchemaError as exc:
            raise HTTPException(422, str(exc)) from exc
        return {"session_id": session_id}

    @app.websocket("/ws/telemetry")
    async def telemetry(websocket: WebSocket) -> None:
        caller = _socket_caller(websocket)
        if caller is None:
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
                ack = store_.ingest(message, caller.driver_id)
                hub.publish(store_.live_view(caller))
                await websocket.send_json(ack)
        except WebSocketDisconnect:
            return

    @app.websocket("/ws/dashboard")
    async def dashboard(websocket: WebSocket) -> None:
        caller = _socket_caller(websocket)
        if caller is None:
            await websocket.close(code=1008)
            return
        await websocket.accept()
        hub: Hub = websocket.app.state.hub
        queue = hub.subscribe()
        await websocket.send_json({"type": "snapshot", **websocket.app.state.store.live_view(caller)})
        try:
            while True:
                snapshot = await queue.get()
                if caller.is_admin or snapshot.get("driver_id") == caller.driver_id:
                    await websocket.send_json({"type": "snapshot", **snapshot})
        except WebSocketDisconnect:
            hub.unsubscribe(queue)

    @app.websocket("/ws/audio")
    async def audio(websocket: WebSocket) -> None:
        caller = _socket_caller(websocket)
        if caller is None:
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
                    lambda question: websocket.app.state.store.ask(question, payload.get("session_id"), caller),
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


def _caller(request: Request) -> Caller:
    caller = _resolve(
        request.headers.get("authorization"),
        request.query_params.get("token"),
        request.app.state,
        request.cookies.get(SESSION_COOKIE),
    )
    if caller is None:
        raise HTTPException(status_code=401, detail="unauthorized")
    return caller


def _require_admin(request: Request) -> Caller:
    caller = _caller(request)
    if not caller.is_admin:
        raise HTTPException(status_code=403, detail="administrator only")
    return caller


def _socket_caller(websocket: WebSocket) -> Caller | None:
    return _resolve(
        websocket.headers.get("authorization"),
        websocket.query_params.get("token"),
        websocket.app.state,
        websocket.cookies.get(SESSION_COOKIE),
    )


def _resolve(header: str | None, query: str | None, state, cookie: str | None = None) -> Caller | None:
    token = None
    if header is not None and header.startswith("Bearer "):
        token = header[7:]
    elif query:
        token = query
    if token:
        return state.store.authenticate(token, state.settings.auth_token)
    if cookie:
        return state.store.authenticate_session(cookie)
    return None


def _public_caller(caller: Caller) -> dict:
    return {
        "role": "administrator" if caller.is_admin else "driver",
        "driver_id": caller.driver_id,
        "display_name": caller.display_name,
    }


def index_file(static_dir: Path | None) -> FileResponse | None:
    if static_dir is None:
        return None
    path = static_dir / "index.html"
    if not path.exists():
        return None
    return FileResponse(path)
