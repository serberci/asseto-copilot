"""Payload models.

Units that are confirmed by the source field name or by the in-game layout
are named with that unit. Fields whose unit still needs an in-game check
keep a neutral name and are listed in docs/telemetry-protocol.md.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

SessionStatus = Literal["off", "replay", "live", "pause"]
SessionType = Literal[
    "unknown",
    "practice",
    "qualify",
    "race",
    "hotlap",
    "time_attack",
    "drift",
    "drag",
]
Flag = Literal["none", "blue", "yellow", "black", "white", "checkered", "penalty"]
# Assetto Corsa shared-memory gear: 0 reverse, 1 neutral, 2 first gear.
Gear = int


def gear_label(gear_raw: int) -> str:
    if gear_raw == 0:
        return "R"
    if gear_raw == 1:
        return "N"
    if gear_raw >= 2:
        return str(gear_raw - 1)
    return "?"


class WheelSample(BaseModel):
    """One tyre, in order FL, FR, RL, RR."""

    model_config = ConfigDict(extra="forbid")

    slip: float
    load: float = Field(description="Source wheelLoad. Expected newtons; confirm on the first session.")
    pressure: float = Field(description="Source wheelsPressure. Expected psi; confirm on the first session.")
    angular_speed_rad_s: float
    wear: float = Field(description="Source tyreWear, unscaled.")
    dirt: float
    core_temp_c: float
    inner_temp_c: float | None = None
    middle_temp_c: float | None = None
    outer_temp_c: float | None = None
    brake_temp_c: float | None = None
    suspension_travel_m: float
    camber_rad: float


class HelloPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent_name: str = Field(min_length=1, max_length=80)
    agent_version: str = Field(min_length=1, max_length=40)
    capabilities: list[str] = Field(default_factory=list)


class HeartbeatPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    physics_rate_hz: float = Field(ge=0)
    graphics_rate_hz: float = Field(ge=0)
    publish_rate_hz: float = Field(ge=0)
    game_running: bool
    shared_memory_open: bool
    backend_connected: bool
    last_physics_packet_id: int | None = None
    last_graphics_packet_id: int | None = None
    last_error: str | None = None


class GoodbyePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=1, max_length=200)


class TelemetryPayload(BaseModel):
    """One normalized sample. Pedals are 0–1. Speed is meters per second."""

    model_config = ConfigDict(extra="forbid")

    physics_packet_id: int
    graphics_packet_id: int
    physics_read_at: datetime
    graphics_read_at: datetime
    physics_stale: bool
    graphics_stale: bool

    session_status: SessionStatus
    session_type: SessionType
    track_id: str = Field(min_length=1, max_length=80)
    track_configuration: str = ""
    track_spline_length_m: float | None = Field(default=None, ge=0)
    car_model: str = Field(min_length=1, max_length=80)
    car_skin: str = ""
    player_nick: str = ""
    sector_count: int = Field(ge=0, le=16)

    completed_laps: int = Field(ge=0)
    lap_number: int = Field(ge=1)
    current_lap_time_ms: int | None = Field(default=None, ge=0)
    last_lap_time_ms: int | None = Field(default=None, ge=0)
    best_lap_time_ms: int | None = Field(default=None, ge=0)
    normalized_progress: float = Field(ge=0, le=1)
    distance_traveled_m: float = Field(ge=0)
    current_sector_index: int = Field(ge=0, le=16)
    last_sector_time_ms: int | None = Field(default=None, ge=0)
    in_pit: bool
    in_pit_lane: bool
    flag: Flag

    speed_mps: float = Field(ge=0, le=200)
    rpm: int = Field(ge=0, le=30000)
    max_rpm: int | None = Field(default=None, ge=0, le=30000)
    gear_raw: int = Field(ge=0, le=15)
    throttle: float = Field(ge=0, le=1)
    brake: float = Field(ge=0, le=1)
    clutch: float = Field(ge=0, le=1)
    steering: float = Field(
        gt=-10000,
        lt=10000,
        description="Raw physics.steerAngle. Expected radians; magnitude must be confirmed in-game.",
    )
    velocity_mps: tuple[float, float, float]
    acceleration_g: tuple[float, float, float]
    heading_rad: float
    pitch_rad: float
    roll_rad: float
    fuel_l: float = Field(ge=0, description="Source physics.fuel. Expected liters; confirm against the in-game readout.")
    turbo_boost: float = 0
    brake_bias: float | None = None
    wheels: list[WheelSample] = Field(min_length=4, max_length=4)
    car_coordinates_m: tuple[float, float, float]
    number_of_tyres_out: int = Field(ge=0, le=4)
    surface_grip: float | None = None
    air_temp_c: float | None = None
    road_temp_c: float | None = None
