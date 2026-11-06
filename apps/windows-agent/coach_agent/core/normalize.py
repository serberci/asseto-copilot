"""Map a shared-memory snapshot into the versioned telemetry payload."""

from __future__ import annotations

from telemetry_schema.models import TelemetryPayload, WheelSample

from coach_agent.core.reader import Snapshot

STATUS = {0: "off", 1: "replay", 2: "live", 3: "pause"}
SESSION = {
    -1: "unknown",
    0: "practice",
    1: "qualify",
    2: "race",
    3: "hotlap",
    4: "time_attack",
    5: "drift",
    6: "drag",
}
FLAG = {
    0: "none",
    1: "blue",
    2: "yellow",
    3: "black",
    4: "white",
    5: "checkered",
    6: "penalty",
}


class NormalizationError(ValueError):
    """A shared-memory field is present but not usable as telemetry."""


def _pedal(name: str, value: float) -> float:
    if value < -0.05 or value > 1.05:
        raise NormalizationError(f"{name} {value:.3f} is outside 0..1; the shared-memory layout may be wrong")
    return min(1.0, max(0.0, value))


def _progress(value: float) -> float:
    if value < -0.02 or value > 1.02:
        raise NormalizationError(
            f"normalized position {value:.3f} is outside 0..1; the shared-memory layout may be wrong"
        )
    return min(1.0, max(0.0, value))


def _milliseconds(value: int) -> int | None:
    if value < 0:
        return None
    return value


def normalize(snapshot: Snapshot) -> TelemetryPayload:
    physics = snapshot.physics
    graphics = snapshot.graphics
    static = snapshot.static
    if not static.track.strip() or not static.car_model.strip():
        raise NormalizationError("track or car is empty; the session is not ready")
    status = STATUS.get(graphics.status)
    session = SESSION.get(graphics.session)
    flag = FLAG.get(graphics.flag)
    if status is None or session is None or flag is None:
        raise NormalizationError("graphics status, session, or flag is not a known Assetto Corsa value")
    if physics.speed_kmh < -1 or physics.speed_kmh > 500:
        raise NormalizationError(f"speed {physics.speed_kmh:.1f} km/h is not plausible")
    if not 0 <= physics.gear <= 15:
        raise NormalizationError(f"gear {physics.gear} is outside 0..15")
    if physics.rpms < 0 or physics.rpms > 30000:
        raise NormalizationError(f"rpm {physics.rpms} is outside 0..30000")

    wheels = [
        WheelSample(
            slip=wheel.slip,
            load=wheel.load,
            pressure=wheel.pressure,
            angular_speed_rad_s=wheel.angular_speed_rad_s,
            wear=wheel.wear,
            dirt=wheel.dirt,
            core_temp_c=wheel.core_temp_c,
            inner_temp_c=wheel.inner_temp_c,
            middle_temp_c=wheel.middle_temp_c,
            outer_temp_c=wheel.outer_temp_c,
            brake_temp_c=wheel.brake_temp_c,
            suspension_travel_m=wheel.suspension_travel_m,
            camber_rad=wheel.camber_rad,
        )
        for wheel in physics.wheels
    ]
    spline = static.spline_length_m if static.spline_length_m > 0 else None
    return TelemetryPayload(
        physics_packet_id=physics.packet_id,
        graphics_packet_id=graphics.packet_id,
        physics_read_at=physics.read_at,
        graphics_read_at=graphics.read_at,
        physics_stale=physics.stale,
        graphics_stale=graphics.stale,
        session_status=status,
        session_type=session,
        track_id=static.track.strip(),
        track_configuration=static.track_configuration.strip(),
        track_spline_length_m=spline,
        car_model=static.car_model.strip(),
        car_skin=static.car_skin.strip(),
        player_nick=static.player_nick.strip(),
        sector_count=max(0, static.sector_count),
        completed_laps=max(0, graphics.completed_laps),
        lap_number=max(1, graphics.completed_laps + 1),
        current_lap_time_ms=_milliseconds(graphics.current_time_ms),
        last_lap_time_ms=_milliseconds(graphics.last_time_ms),
        best_lap_time_ms=_milliseconds(graphics.best_time_ms),
        normalized_progress=_progress(graphics.normalized_position),
        distance_traveled_m=max(0.0, graphics.distance_traveled_m),
        current_sector_index=max(0, graphics.sector_index),
        last_sector_time_ms=_milliseconds(graphics.last_sector_time_ms),
        in_pit=graphics.in_pit,
        in_pit_lane=graphics.in_pit_lane,
        flag=flag,
        speed_mps=max(0.0, physics.speed_kmh) / 3.6,
        rpm=physics.rpms,
        max_rpm=static.max_rpm if static.max_rpm > 0 else None,
        gear_raw=physics.gear,
        throttle=_pedal("throttle", physics.gas),
        brake=_pedal("brake", physics.brake),
        clutch=_pedal("clutch", physics.clutch),
        steering=physics.steer_angle,
        velocity_mps=physics.velocity,
        acceleration_g=physics.acceleration_g,
        heading_rad=physics.heading,
        pitch_rad=physics.pitch,
        roll_rad=physics.roll,
        fuel_l=max(0.0, physics.fuel),
        turbo_boost=physics.turbo_boost,
        brake_bias=physics.brake_bias,
        wheels=wheels,
        car_coordinates_m=graphics.coordinates,
        number_of_tyres_out=max(0, min(4, physics.number_of_tyres_out)),
        surface_grip=graphics.surface_grip,
        air_temp_c=physics.air_temp,
        road_temp_c=physics.road_temp,
    )
