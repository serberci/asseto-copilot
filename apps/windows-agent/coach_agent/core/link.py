"""Latest-value publisher with reconnect backoff.

Telemetry is not a log. A failed send keeps the newest sample and the next
successful connection delivers that sample, not a burst of stale ones.
"""

from __future__ import annotations

import json
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field

from telemetry_schema.messages import HelloMessage, Message


class LinkSocket:
    def send_text(self, text: str) -> None:
        raise NotImplementedError

    def recv_text(self, timeout: float) -> str | None:
        raise NotImplementedError

    def close(self) -> None:
        raise NotImplementedError


Connector = Callable[[], LinkSocket]


@dataclass
class OutboundLink:
    connector: Connector
    hello_factory: Callable[[], HelloMessage]
    sleeper: Callable[[float], None] = time.sleep
    clock: Callable[[], float] = time.monotonic
    state: str = "disconnected"
    session_id: str | None = None
    last_error: str | None = None
    attempts: int = 0
    _socket: LinkSocket | None = field(default=None, init=False, repr=False)
    _latest: dict[str, Message] = field(default_factory=dict, init=False, repr=False)
    _backoff: float = field(default=0.5, init=False)
    _next_attempt: float = field(default=0.0, init=False)
    _stopped: bool = field(default=False, init=False)
    _thread: threading.Thread | None = field(default=None, init=False, repr=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)

    def submit(self, message: Message) -> None:
        if message.session_id is None and self.session_id is not None:
            message = message.model_copy(update={"session_id": self.session_id})
        with self._lock:
            self._latest[message.type] = message

    def start(self) -> None:
        if self._thread is not None:
            return
        self._stopped = False
        self._thread = threading.Thread(target=self._loop, name="coach-link", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stopped = True
        if self._thread is not None:
            self._thread.join(timeout=2)
            self._thread = None
        self._drop()

    def pump(self) -> None:
        """One non-blocking step. Tests call this directly; `start` calls it in a thread."""

        now = self.clock()
        with self._lock:
            socket = self._socket
        if socket is None:
            if now < self._next_attempt:
                return
            self.state = "connecting"
            try:
                socket = self.connector()
            except Exception as exc:
                self._fail(str(exc), now)
                return
            with self._lock:
                self._socket = socket
                self.attempts += 1
            self.state = "connected"
            self._backoff = 0.5
            self.last_error = None
            try:
                self._send(self.hello_factory())
                self._receive()
            except Exception as exc:
                self._fail(str(exc), now)
                return
        try:
            self._receive()
            with self._lock:
                pending = list(self._latest.items())
            for kind, message in pending:
                self._send(message)
                with self._lock:
                    if self._latest.get(kind) is message:
                        self._latest.pop(kind, None)
        except Exception as exc:
            self._fail(str(exc), now)

    def _loop(self) -> None:
        while not self._stopped:
            self.pump()
            self.sleeper(0.02)

    def _send(self, message: Message) -> None:
        socket = self._socket
        if socket is None:
            raise ConnectionError("not connected")
        socket.send_text(message.model_dump_json())

    def _receive(self) -> None:
        socket = self._socket
        if socket is None:
            return
        while True:
            raw = socket.recv_text(0)
            if raw is None:
                return
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict) and payload.get("type") == "ack" and payload.get("session_id"):
                self.session_id = str(payload["session_id"])

    def _fail(self, error: str, now: float) -> None:
        self.last_error = error
        self.state = "disconnected"
        self._drop()
        self._next_attempt = now + self._backoff
        self._backoff = min(self._backoff * 2, 10.0)

    def _drop(self) -> None:
        with self._lock:
            socket = self._socket
            self._socket = None
        if socket is not None:
            try:
                socket.close()
            except Exception:
                pass


class WebSocketAdapter(LinkSocket):
    def __init__(self, socket) -> None:
        self._socket = socket

    def send_text(self, text: str) -> None:
        self._socket.send(text)

    def recv_text(self, timeout: float) -> str | None:
        try:
            message = self._socket.recv(timeout=timeout)
        except TimeoutError:
            return None
        if isinstance(message, bytes):
            return message.decode("utf-8")
        return str(message)

    def close(self) -> None:
        self._socket.close()


def websocket_connector(url: str, token: str) -> Connector:
    def connect() -> LinkSocket:
        from websockets.sync.client import connect as open_socket

        socket = open_socket(
            url,
            additional_headers={"Authorization": f"Bearer {token}"},
            open_timeout=5,
        )
        return WebSocketAdapter(socket)

    return connect
