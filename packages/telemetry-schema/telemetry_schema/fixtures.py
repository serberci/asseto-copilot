"""Synthetic session used by tests and the dashboard when the game is not running.

The track id is `synthetic-oval`. It is not a real circuit and must not be
treated as calibrated track data for a real car.
"""

from datetime import datetime, timedelta, timezone

from telemetry_schema.messages import (
    SCHEMA_VERSION,
    HeartbeatMessage,
    HelloMessage,
    TelemetryMessage,
)
from telemetry_schema.models import (
    HeartbeatPayload,
    HelloPayload,
    TelemetryPayload,
    WheelSample,
)

AGENT_ID = "fixture-agent"
TRACK_ID = "synthetic-oval"
CAR_MODEL = "synthetic-car"


def _wheels() -> list[WheelSample]:
    return [
        WheelSample(
            slip=0.02,
            load=3500,
            pressure=28,
            angular_speed_rad_s=80,
            wear=0,
            dirt=0,
            core_temp_c=80,
            inner_temp_c=85,
            middle_temp_c=80,
            outer_temp_c=75,
            brake_temp_c=200,
            suspension_travel_m=0.05,
            camber_rad=-0.03,
        )
        for _ in range(4)
    ]


def _speed(progress: float, *, earlier_brake: bool) -> float:
    """Piecewise speed that keeps entry speed identical for both laps."""

    if progress < 0.40:
        return 50.0
    if earlier_brake:
        if progress < 0.50:
            return 50.0 - (progress - 0.40) / 0.10 * 17.0
        if progress < 0.60:
            return 33.0 + (progress - 0.50) / 0.10 * 11.0
        return 44.0
    if progress < 0.46:
        return 50.0
    if progress < 0.50:
        return 50.0 - (progress - 0.46) / 0.04 * 15.0
    if progress < 0.60:
        return 35.0 + (progress - 0.50) / 0.10 * 13.0
    return 48.0


def _pedals(progress: float, *, earlier_brake: bool) -> tuple[float, float]:
    if earlier_brake:
        braking = 0.42 <= progress < 0.50
        throttle = 0.0 if progress < 0.57 else 1.0
    else:
        braking = 0.46 <= progress < 0.50
        throttle = 0.0 if progress < 0.52 else 1.0
    if braking:
        return 0.0, 0.9
    return throttle, 0.0


def _elapsed(progress: float, *, earlier_brake: bool) -> float:
    base = progress * 30.0
    if not earlier_brake or progress <= 0.40:
        return base
    if progress >= 0.60:
        return base + 0.4
    return base + 0.4 * (progress - 0.40) / 0.20


def synthetic_session(start: datetime | None = None) -> list[HelloMessage | TelemetryMessage | HeartbeatMessage]:
    """Two complete laps. The second brakes earlier and loses 0.4 s by corner exit."""

    origin = start or datetime(2026, 11, 6, 12, 0, tzinfo=timezone.utc)
    messages: list[HelloMessage | TelemetryMessage | HeartbeatMessage] = [
        HelloMessage(
            schema_version=SCHEMA_VERSION,
            game="assetto_corsa",
            agent_id=AGENT_ID,
            session_id=None,
            sequence=0,
            timestamp=origin,
            type="hello",
            payload=HelloPayload(
                agent_name="Assetto Corsa Coach Agent",
                agent_version="0.1.0",
                capabilities=["telemetry"],
            ),
        )
    ]
    sequence = 1
    steps = 51

    def add_sample(
        *,
        lap_index: int,
        progress: float,
        earlier: bool,
        completed_laps: int,
        lap_number: int,
        current_lap_time_ms: int | None,
        last_lap_time_ms: int | None,
        best_lap_time_ms: int | None,
        session_elapsed: float,
    ) -> None:
        nonlocal sequence
        moment = origin + timedelta(seconds=session_elapsed)
        throttle, brake = _pedals(progress, earlier_brake=earlier)
        speed = _speed(progress, earlier_brake=earlier)
        payload = TelemetryPayload(
            physics_packet_id=sequence,
            graphics_packet_id=sequence,
            physics_read_at=moment,
            graphics_read_at=moment,
            physics_stale=False,
            graphics_stale=False,
            session_status="live",
            session_type="practice",
            track_id=TRACK_ID,
            track_configuration="",
            track_spline_length_m=4000.0,
            car_model=CAR_MODEL,
            car_skin="default",
            player_nick="driver",
            sector_count=3,
            completed_laps=completed_laps,
            lap_number=lap_number,
            current_lap_time_ms=current_lap_time_ms,
            last_lap_time_ms=last_lap_time_ms,
            best_lap_time_ms=best_lap_time_ms,
            normalized_progress=progress,
            distance_traveled_m=progress * 4000.0,
            current_sector_index=0 if progress < 0.33 else 1 if progress < 0.66 else 2,
            last_sector_time_ms=None,
            in_pit=False,
            in_pit_lane=False,
            flag="none",
            speed_mps=speed,
            rpm=6000,
            max_rpm=8000,
            gear_raw=4,
            throttle=throttle,
            brake=brake,
            clutch=0.0,
            steering=0.05 if 0.40 <= progress <= 0.60 else 0.0,
            velocity_mps=(speed, 0.0, 0.0),
            acceleration_g=(0.0, 0.0, 0.0),
            heading_rad=0.0,
            pitch_rad=0.0,
            roll_rad=0.0,
            fuel_l=40.0,
            turbo_boost=0.0,
            brake_bias=0.65,
            wheels=_wheels(),
            car_coordinates_m=(progress * 100.0, 0.0, 0.0),
            number_of_tyres_out=0,
            surface_grip=1.0,
            air_temp_c=22.0,
            road_temp_c=28.0,
        )
        messages.append(
            TelemetryMessage(
                schema_version=SCHEMA_VERSION,
                game="assetto_corsa",
                agent_id=AGENT_ID,
                session_id=None,
                sequence=sequence,
                timestamp=moment,
                type="telemetry",
                payload=payload,
            )
        )
        sequence += 1

    session_offset = 0.0
    for lap_index, earlier in enumerate((False, True)):
        for step in range(0 if lap_index == 0 else 1, steps):
            progress = step / (steps - 1)
            lap_elapsed = _elapsed(progress, earlier_brake=earlier)
            add_sample(
                lap_index=lap_index,
                progress=progress,
                earlier=earlier,
                completed_laps=lap_index,
                lap_number=lap_index + 1,
                current_lap_time_ms=int(round(lap_elapsed * 1000)),
                last_lap_time_ms=30000 if lap_index else None,
                best_lap_time_ms=30000 if lap_index else None,
                session_elapsed=session_offset + lap_elapsed,
            )
        lap_elapsed = _elapsed(1.0, earlier_brake=earlier)
        lap_ms = int(round(lap_elapsed * 1000))
        session_offset += lap_elapsed
        add_sample(
            lap_index=lap_index,
            progress=0.0,
            earlier=False,
            completed_laps=lap_index + 1,
            lap_number=lap_index + 2,
            current_lap_time_ms=0,
            last_lap_time_ms=lap_ms,
            best_lap_time_ms=30000 if lap_ms >= 30000 else lap_ms,
            session_elapsed=session_offset,
        )
    messages.append(
        HeartbeatMessage(
            schema_version=SCHEMA_VERSION,
            game="assetto_corsa",
            agent_id=AGENT_ID,
            session_id=None,
            sequence=sequence,
            timestamp=origin + timedelta(seconds=61),
            type="heartbeat",
            payload=HeartbeatPayload(
                physics_rate_hz=50,
                graphics_rate_hz=50,
                publish_rate_hz=20,
                game_running=True,
                shared_memory_open=True,
                backend_connected=True,
            ),
        )
    )
    return messages
