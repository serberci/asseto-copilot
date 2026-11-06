from collections import deque

from telemetry_schema.models import TelemetryPayload


class RingBuffer:
    """Short in-memory history. The default holds about 30 seconds at 100 Hz."""

    def __init__(self, capacity: int = 3000) -> None:
        self._items: deque[TelemetryPayload] = deque(maxlen=max(1, capacity))

    def append(self, sample: TelemetryPayload) -> None:
        self._items.append(sample)

    def latest(self) -> TelemetryPayload | None:
        if not self._items:
            return None
        return self._items[-1]

    def __len__(self) -> int:
        return len(self._items)
