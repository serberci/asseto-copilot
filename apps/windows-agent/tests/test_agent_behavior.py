from datetime import datetime, timedelta, timezone

from telemetry_schema.messages import SCHEMA_VERSION, HelloMessage
from telemetry_schema.models import HelloPayload

from coach_agent.audio.talk import PushToTalk
from coach_agent.core.agent import Clock, CoachAgent
from coach_agent.core.game import MemoryRunKey, apply_launch_at_login, game_is_running
from coach_agent.config.settings import AgentSettings
from coach_agent.core.layouts import GraphicsPage, PhysicsPage, StaticPage, page_bytes
from coach_agent.core.link import LinkSocket, OutboundLink
from coach_agent.core.mapping import BufferSharedMemory
from coach_agent.core.reader import SnapshotReader


def _text(array, value: str) -> None:
    for index, character in enumerate(value):
        array[index] = ord(character)


def _pages(speed_kmh: float = 180, gear: int = 4, gas: float = 0.5, packet: int = 1):
    del speed_kmh, gear, gas
    physics = PhysicsPage()
    physics.packetId = packet
    physics.speedKmh = 180
    physics.gear = 4
    physics.gas = 0.5
    physics.brake = 0
    physics.rpms = 6400
    graphics = GraphicsPage()
    graphics.packetId = packet
    graphics.status = 2
    graphics.session = 0
    graphics.completedLaps = 0
    graphics.iCurrentTime = 1000
    graphics.normalizedCarPosition = 0.2
    static = StaticPage()
    static.maxRpm = 8000
    static.sectorCount = 3
    _text(static.track, "imola")
    _text(static.carModel, "ks_ferrari_458")
    return physics, graphics, static


class ManualClock(Clock):
    def __init__(self) -> None:
        self.now = 0.0
        self.moment = datetime(2026, 11, 6, tzinfo=timezone.utc)

    def mono(self) -> float:
        return self.now

    def wall(self) -> datetime:
        return self.moment

    def advance(self, seconds: float) -> None:
        self.now += seconds
        self.moment += timedelta(seconds=seconds)


class FakeSocket(LinkSocket):
    def __init__(self) -> None:
        self.sent: list[str] = []
        self._inbound = ['{"type":"ack","session_id":"session-1","sequence":1}']
        self.closed = False

    def send_text(self, text: str) -> None:
        if self.closed:
            raise ConnectionError("closed")
        self.sent.append(text)

    def recv_text(self, timeout: float) -> str | None:
        del timeout
        if not self._inbound:
            return None
        return self._inbound.pop(0)

    def close(self) -> None:
        self.closed = True


def test_game_process_name_is_acs_exe():
    assert game_is_running(["ACS.EXE", "chrome.exe"]) is True
    assert game_is_running(["acc.exe"]) is False


def test_launch_at_login_writes_and_removes_the_run_value():
    store = MemoryRunKey()
    apply_launch_at_login(store, True, r'"C:\Coach\Agent.exe" --minimized')
    assert "Agent.exe" in store.get("AssettoCorsaCoachAgent")
    apply_launch_at_login(store, False, "")
    assert store.get("AssettoCorsaCoachAgent") is None


def test_push_to_talk_returns_one_clip_per_press():
    talk = PushToTalk()
    assert talk.key_up() is None
    talk.add_frame(b"ignored")
    talk.key_down()
    talk.add_frame(b"abc")
    talk.key_down()
    talk.add_frame(b"de")
    assert talk.key_up() == b"abcde"
    assert talk.key_up() is None


def test_reconnect_backs_off_then_keeps_the_latest_sample():
    clock = ManualClock()
    sockets: list[FakeSocket] = []
    failures = {"left": 2}

    def connector():
        if failures["left"]:
            failures["left"] -= 1
            raise ConnectionError("down")
        socket = FakeSocket()
        sockets.append(socket)
        return socket

    link = OutboundLink(connector=connector, hello_factory=lambda: _hello(), clock=clock.mono)
    link.submit(_hello())
    link.pump()
    clock.advance(0.4)
    link.pump()
    assert failures["left"] == 1
    clock.advance(0.6)
    link.pump()
    clock.advance(1.1)
    link.pump()
    assert link.state == "connected"
    assert link.session_id == "session-1"
    assert sockets[0].sent


def _hello() -> HelloMessage:
    return HelloMessage(
        schema_version=SCHEMA_VERSION,
        game="assetto_corsa",
        agent_id="agent",
        session_id=None,
        sequence=0,
        timestamp=datetime(2026, 11, 6, tzinfo=timezone.utc),
        type="hello",
        payload=HelloPayload(agent_name="Assetto Corsa Coach Agent", agent_version="0.1.0"),
    )


def test_stale_pages_are_not_published_twice():
    clock = ManualClock()
    physics, graphics, static = _pages(packet=1)
    source = BufferSharedMemory(page_bytes(physics), page_bytes(graphics), page_bytes(static))
    sent: list[str] = []

    class CollectingLink:
        state = "disconnected"
        session_id = None
        last_error = None

        def submit(self, message) -> None:
            sent.append(message.type)

        def stop(self) -> None:
            return None

    settings = AgentSettings(publish_hz=20, heartbeat_s=10, physics_hz=100)
    agent = CoachAgent(
        settings,
        CollectingLink(),
        lambda: SnapshotReader(source),
        clock=clock,
        fixture_mode=True,
    )
    agent.tick()
    agent.tick()
    telemetry = [kind for kind in sent if kind == "telemetry"]
    assert telemetry == ["telemetry"]
    physics.packetId = 2
    graphics.packetId = 2
    source.physics = page_bytes(physics)
    source.graphics = page_bytes(graphics)
    clock.advance(0.06)
    agent.tick()
    assert [kind for kind in sent if kind == "telemetry"] == ["telemetry", "telemetry"]


def test_publish_waits_for_the_configured_interval():
    clock = ManualClock()
    sent: list[str] = []

    class CollectingLink:
        state = "connected"
        session_id = "s"
        last_error = None

        def submit(self, message) -> None:
            sent.append(message.type)

        def stop(self) -> None:
            return None

    # Each tick needs a new reader only once; mutate the open source instead.
    physics, graphics, static = _pages(packet=1)
    source = BufferSharedMemory(page_bytes(physics), page_bytes(graphics), page_bytes(static))
    settings = AgentSettings(publish_hz=10, heartbeat_s=100, physics_hz=100)
    agent = CoachAgent(settings, CollectingLink(), lambda: SnapshotReader(source), clock=clock, fixture_mode=True)
    agent.tick()
    physics.packetId = 2
    graphics.packetId = 2
    source.physics = page_bytes(physics)
    source.graphics = page_bytes(graphics)
    clock.advance(0.02)
    agent.tick()
    assert sent.count("telemetry") == 1
    clock.advance(0.1)
    physics.packetId = 3
    graphics.packetId = 3
    source.physics = page_bytes(physics)
    source.graphics = page_bytes(graphics)
    agent.tick()
    assert sent.count("telemetry") == 2
