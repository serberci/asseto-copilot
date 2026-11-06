import json
from datetime import datetime, timezone

import pytest

from telemetry_schema import SchemaError, gear_label, parse_envelope, synthetic_session
from telemetry_schema.messages import SCHEMA_VERSION


def test_gear_labels_follow_assetto_corsa_convention():
    assert gear_label(0) == "R"
    assert gear_label(1) == "N"
    assert gear_label(2) == "1"
    assert gear_label(4) == "3"


def test_naive_timestamp_and_unknown_version_are_rejected():
    sample = synthetic_session()[1].model_dump(mode="json")
    sample["timestamp"] = "2026-11-06T12:00:00"
    with pytest.raises(SchemaError):
        parse_envelope(sample)

    sample = synthetic_session()[1].model_dump(mode="json")
    sample["schema_version"] = "9.0.0"
    with pytest.raises(SchemaError):
        parse_envelope(sample)


def test_unknown_message_type_and_extra_fields_are_rejected():
    with pytest.raises(SchemaError):
        parse_envelope({"type": "setup", "schema_version": SCHEMA_VERSION})

    sample = synthetic_session()[1].model_dump(mode="json")
    sample["payload"]["invented_metric"] = 1
    with pytest.raises(SchemaError):
        parse_envelope(sample)


def test_synthetic_session_parses_and_second_lap_loses_time_after_the_corner():
    messages = synthetic_session(datetime(2026, 11, 6, tzinfo=timezone.utc))
    restored = [parse_envelope(json.loads(item.model_dump_json())) for item in messages]
    telemetry = [item for item in restored if item.type == "telemetry"]
    assert telemetry[0].payload.speed_mps == pytest.approx(50)
    assert telemetry[0].payload.track_id == "synthetic-oval"

    def at(lap: int, progress: float):
        return next(
            item.payload
            for item in telemetry
            if item.payload.lap_number == lap and item.payload.normalized_progress == pytest.approx(progress)
        )

    def lap_seconds(lap: int, progress: float) -> float:
        sample = at(lap, progress)
        start = at(lap, 0.0)
        return (sample.physics_read_at - start.physics_read_at).total_seconds()

    assert at(1, 0.40).speed_mps == pytest.approx(at(2, 0.40).speed_mps)
    assert at(1, 0.40).brake == 0
    assert at(2, 0.42).brake == pytest.approx(0.9)
    assert at(1, 0.46).brake == pytest.approx(0.9)
    assert lap_seconds(2, 0.60) - lap_seconds(1, 0.60) == pytest.approx(0.4, abs=0.02)
