import ctypes
from datetime import datetime, timedelta, timezone

import pytest

from coach_agent.core.layouts import (
    GRAPHICS_BYTES,
    PHYSICS_BYTES,
    STATIC_BYTES,
    GraphicsPage,
    PhysicsPage,
    StaticPage,
    page_bytes,
    read_physics_page,
)
from coach_agent.core.mapping import BufferSharedMemory
from coach_agent.core.normalize import NormalizationError, normalize
from coach_agent.core.reader import SnapshotReader


def _text(array, value: str) -> None:
    for index, character in enumerate(value):
        array[index] = ord(character)


def _pages(speed_kmh: float = 180, gear: int = 4, gas: float = 0.5, packet: int = 1):
    physics = PhysicsPage()
    physics.packetId = packet
    physics.speedKmh = speed_kmh
    physics.gear = gear
    physics.gas = gas
    physics.brake = 0.25
    physics.clutch = 0
    physics.rpms = 6400
    physics.steerAngle = 0.2
    physics.fuel = 30
    graphics = GraphicsPage()
    graphics.packetId = packet
    graphics.status = 2
    graphics.session = 0
    graphics.completedLaps = 0
    graphics.iCurrentTime = 12000
    graphics.normalizedCarPosition = 0.4
    graphics.distanceTraveled = 1600
    static = StaticPage()
    static.maxRpm = 8000
    static.sectorCount = 3
    static.trackSPlineLength = 4000
    _text(static.track, "imola")
    _text(static.carModel, "ks_ferrari_458")
    _text(static.playerNick, "sergi")
    return physics, graphics, static


def test_page_layout_matches_the_in_game_shared_memory_prefix():
    assert ctypes.sizeof(PhysicsPage) == PHYSICS_BYTES == 580
    assert ctypes.sizeof(GraphicsPage) == GRAPHICS_BYTES == 296
    assert ctypes.sizeof(StaticPage) == STATIC_BYTES == 684
    assert PhysicsPage.speedKmh.offset == 28
    assert PhysicsPage.gear.offset == 16
    assert PhysicsPage.localVelocity.offset == 568
    assert GraphicsPage.completedLaps.offset == 132
    assert GraphicsPage.normalizedCarPosition.offset == 248
    assert StaticPage.track.offset == 134
    assert StaticPage.carModel.offset == 68


def test_speed_gear_and_pedals_are_converted_from_the_game_page():
    physics, graphics, static = _pages()
    reader = SnapshotReader(BufferSharedMemory(page_bytes(physics), page_bytes(graphics), page_bytes(static)))
    moment = datetime(2026, 11, 6, tzinfo=timezone.utc)
    payload = normalize(reader.read(moment))
    assert payload.speed_mps == pytest.approx(50)
    assert payload.gear_raw == 4
    assert payload.throttle == pytest.approx(0.5)
    assert payload.brake == pytest.approx(0.25)
    assert payload.rpm == 6400
    assert payload.lap_number == 1
    assert payload.normalized_progress == pytest.approx(0.4)
    assert payload.track_id == "imola"
    assert payload.car_model == "ks_ferrari_458"
    assert payload.physics_stale is False


def test_repeated_packet_is_stale_and_a_new_packet_is_fresh():
    physics, graphics, static = _pages(packet=3)
    source = BufferSharedMemory(page_bytes(physics), page_bytes(graphics), page_bytes(static))
    reader = SnapshotReader(source)
    moment = datetime(2026, 11, 6, tzinfo=timezone.utc)
    first = reader.read(moment)
    second = reader.read(moment + timedelta(milliseconds=10))
    assert first.physics.stale is False
    assert second.physics.stale is True
    assert second.graphics.stale is True
    physics.packetId = 4
    source.physics = page_bytes(physics)
    third = reader.read(moment + timedelta(milliseconds=20))
    assert third.physics.stale is False
    assert third.graphics.stale is True


def test_implausible_pedal_is_rejected():
    physics, graphics, static = _pages(gas=1.5)
    reader = SnapshotReader(BufferSharedMemory(page_bytes(physics), page_bytes(graphics), page_bytes(static)))
    with pytest.raises(NormalizationError):
        normalize(reader.read(datetime(2026, 11, 6, tzinfo=timezone.utc)))


def test_short_page_is_rejected():
    with pytest.raises(Exception):
        read_physics_page(b"\x00\x01")
