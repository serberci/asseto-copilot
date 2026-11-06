from datetime import datetime
from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, ValidationError, field_validator

from telemetry_schema.errors import SchemaError
from telemetry_schema.models import GoodbyePayload, HeartbeatPayload, HelloPayload, TelemetryPayload

SCHEMA_VERSION = "1.0.0"
SUPPORTED_SCHEMA_VERSIONS = frozenset({SCHEMA_VERSION})
GAME = "assetto_corsa"


class _Message(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str
    game: Literal["assetto_corsa"]
    agent_id: str = Field(min_length=1, max_length=80)
    session_id: str | None = Field(default=None, max_length=80)
    sequence: Annotated[int, Field(ge=0)]
    timestamp: AwareDatetime

    @field_validator("schema_version")
    @classmethod
    def _supported_version(cls, value: str) -> str:
        if value not in SUPPORTED_SCHEMA_VERSIONS:
            raise ValueError(f"unsupported schema_version {value!r}")
        return value


class HelloMessage(_Message):
    type: Literal["hello"]
    payload: HelloPayload


class TelemetryMessage(_Message):
    type: Literal["telemetry"]
    payload: TelemetryPayload


class HeartbeatMessage(_Message):
    type: Literal["heartbeat"]
    payload: HeartbeatPayload


class GoodbyeMessage(_Message):
    type: Literal["goodbye"]
    payload: GoodbyePayload


Message = HelloMessage | TelemetryMessage | HeartbeatMessage | GoodbyeMessage

_MODELS: dict[str, type[_Message]] = {
    "hello": HelloMessage,
    "telemetry": TelemetryMessage,
    "heartbeat": HeartbeatMessage,
    "goodbye": GoodbyeMessage,
}


def parse_envelope(data: object) -> Message:
    """Validate one JSON object at the agent/backend boundary."""

    if not isinstance(data, dict):
        raise SchemaError("telemetry message must be a JSON object")
    kind = data.get("type")
    model = _MODELS.get(kind) if isinstance(kind, str) else None
    if model is None:
        raise SchemaError(f"unsupported message type: {kind!r}")
    try:
        return model.model_validate(data)
    except ValidationError as exc:
        raise SchemaError(str(exc)) from exc


def message_timestamp(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise SchemaError("timestamp must be timezone-aware")
    return value
