"""Versioned telemetry messages shared by the Windows agent and the AI host."""

from telemetry_schema.errors import SchemaError
from telemetry_schema.fixtures import reference_session, synthetic_session
from telemetry_schema.messages import (
    SCHEMA_VERSION,
    SUPPORTED_SCHEMA_VERSIONS,
    GoodbyeMessage,
    HeartbeatMessage,
    HelloMessage,
    Message,
    TelemetryMessage,
    parse_envelope,
)
from telemetry_schema.models import (
    Gear,
    HeartbeatPayload,
    HelloPayload,
    TelemetryPayload,
    WheelSample,
    gear_label,
)

__all__ = [
    "SCHEMA_VERSION",
    "SUPPORTED_SCHEMA_VERSIONS",
    "Gear",
    "GoodbyeMessage",
    "HeartbeatMessage",
    "HeartbeatPayload",
    "HelloMessage",
    "HelloPayload",
    "Message",
    "SchemaError",
    "TelemetryMessage",
    "TelemetryPayload",
    "WheelSample",
    "gear_label",
    "parse_envelope",
    "reference_session",
    "synthetic_session",
]
