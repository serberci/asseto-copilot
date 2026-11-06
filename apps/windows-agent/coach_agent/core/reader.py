"""Parse shared-memory pages and remember which packet ids are new."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from coach_agent.core.layouts import (
    decode_text,
    read_graphics_page,
    read_physics_page,
    read_static_page,
)
from coach_agent.core.mapping import BufferSharedMemory, WindowsSharedMemory


@dataclass(frozen=True)
class WheelRaw:
    slip: float
    load: float
    pressure: float
    angular_speed_rad_s: float
    wear: float
    dirt: float
    core_temp_c: float
    inner_temp_c: float
    middle_temp_c: float
    outer_temp_c: float
    brake_temp_c: float
    suspension_travel_m: float
    camber_rad: float


@dataclass(frozen=True)
class PhysicsRead:
    read_at: datetime
    packet_id: int
    stale: bool
    gas: float
    brake: float
    clutch: float
    fuel: float
    gear: int
    rpms: int
    steer_angle: float
    speed_kmh: float
    velocity: tuple[float, float, float]
    acceleration_g: tuple[float, float, float]
    heading: float
    pitch: float
    roll: float
    turbo_boost: float
    brake_bias: float
    number_of_tyres_out: int
    air_temp: float
    road_temp: float
    wheels: tuple[WheelRaw, WheelRaw, WheelRaw, WheelRaw]


@dataclass(frozen=True)
class GraphicsRead:
    read_at: datetime
    packet_id: int
    stale: bool
    status: int
    session: int
    completed_laps: int
    current_time_ms: int
    last_time_ms: int
    best_time_ms: int
    normalized_position: float
    distance_traveled_m: float
    sector_index: int
    last_sector_time_ms: int
    in_pit: bool
    in_pit_lane: bool
    flag: int
    coordinates: tuple[float, float, float]
    surface_grip: float


@dataclass(frozen=True)
class StaticRead:
    track: str
    track_configuration: str
    car_model: str
    car_skin: str
    player_nick: str
    sector_count: int
    max_rpm: int
    spline_length_m: float


@dataclass(frozen=True)
class Snapshot:
    physics: PhysicsRead
    graphics: GraphicsRead
    static: StaticRead


def _vec3(values) -> tuple[float, float, float]:
    return (float(values[0]), float(values[1]), float(values[2]))


def _wheels(page) -> tuple[WheelRaw, WheelRaw, WheelRaw, WheelRaw]:
    wheels = []
    for index in range(4):
        wheels.append(
            WheelRaw(
                slip=float(page.wheelSlip[index]),
                load=float(page.wheelLoad[index]),
                pressure=float(page.wheelsPressure[index]),
                angular_speed_rad_s=float(page.wheelAngularSpeed[index]),
                wear=float(page.tyreWear[index]),
                dirt=float(page.tyreDirtyLevel[index]),
                core_temp_c=float(page.tyreCoreTemperature[index]),
                inner_temp_c=float(page.tyreTempI[index]),
                middle_temp_c=float(page.tyreTempM[index]),
                outer_temp_c=float(page.tyreTempO[index]),
                brake_temp_c=float(page.brakeTemp[index]),
                suspension_travel_m=float(page.suspensionTravel[index]),
                camber_rad=float(page.camberRAD[index]),
            )
        )
    return (wheels[0], wheels[1], wheels[2], wheels[3])


class SnapshotReader:
    def __init__(self, source: BufferSharedMemory | WindowsSharedMemory) -> None:
        self._source = source
        self._physics_packet: int | None = None
        self._graphics_packet: int | None = None

    def read(self, read_at: datetime) -> Snapshot:
        physics_blob = self._source.read_physics()
        graphics_blob = self._source.read_graphics()
        static_blob = self._source.read_static()
        physics_page = read_physics_page(physics_blob)
        graphics_page = read_graphics_page(graphics_blob)
        static_page = read_static_page(static_blob)

        physics_id = int(physics_page.packetId)
        graphics_id = int(graphics_page.packetId)
        physics_stale = self._physics_packet is not None and physics_id == self._physics_packet
        graphics_stale = self._graphics_packet is not None and graphics_id == self._graphics_packet
        self._physics_packet = physics_id
        self._graphics_packet = graphics_id

        physics = PhysicsRead(
            read_at=read_at,
            packet_id=physics_id,
            stale=physics_stale,
            gas=float(physics_page.gas),
            brake=float(physics_page.brake),
            clutch=float(physics_page.clutch),
            fuel=float(physics_page.fuel),
            gear=int(physics_page.gear),
            rpms=int(physics_page.rpms),
            steer_angle=float(physics_page.steerAngle),
            speed_kmh=float(physics_page.speedKmh),
            velocity=_vec3(physics_page.velocity),
            acceleration_g=_vec3(physics_page.accG),
            heading=float(physics_page.heading),
            pitch=float(physics_page.pitch),
            roll=float(physics_page.roll),
            turbo_boost=float(physics_page.turboBoost),
            brake_bias=float(physics_page.brakeBias),
            number_of_tyres_out=int(physics_page.numberOfTyresOut),
            air_temp=float(physics_page.airTemp),
            road_temp=float(physics_page.roadTemp),
            wheels=_wheels(physics_page),
        )
        graphics = GraphicsRead(
            read_at=read_at,
            packet_id=graphics_id,
            stale=graphics_stale,
            status=int(graphics_page.status),
            session=int(graphics_page.session),
            completed_laps=int(graphics_page.completedLaps),
            current_time_ms=int(graphics_page.iCurrentTime),
            last_time_ms=int(graphics_page.iLastTime),
            best_time_ms=int(graphics_page.iBestTime),
            normalized_position=float(graphics_page.normalizedCarPosition),
            distance_traveled_m=float(graphics_page.distanceTraveled),
            sector_index=int(graphics_page.currentSectorIndex),
            last_sector_time_ms=int(graphics_page.lastSectorTime),
            in_pit=bool(graphics_page.isInPit),
            in_pit_lane=bool(graphics_page.isInPitLine),
            flag=int(graphics_page.flag),
            coordinates=_vec3(graphics_page.carCoordinates),
            surface_grip=float(graphics_page.surfaceGrip),
        )
        static = StaticRead(
            track=decode_text(static_page.track),
            track_configuration=decode_text(static_page.trackConfiguration),
            car_model=decode_text(static_page.carModel),
            car_skin=decode_text(static_page.carSkin),
            player_nick=decode_text(static_page.playerNick),
            sector_count=int(static_page.sectorCount),
            max_rpm=int(static_page.maxRpm),
            spline_length_m=float(static_page.trackSPlineLength),
        )
        return Snapshot(physics=physics, graphics=graphics, static=static)

    def close(self) -> None:
        self._source.close()
