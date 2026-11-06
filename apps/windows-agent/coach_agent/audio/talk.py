"""Push-to-talk state. Capture hardware stays behind this small machine.

Wake word detection is intentionally absent. The gaming PC owns the
microphone and the headset; this module only decides when a clip starts
and ends.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class PushToTalk:
    recording: bool = False
    _frames: list[bytes] = field(default_factory=list)

    def key_down(self) -> None:
        if self.recording:
            return
        self.recording = True
        self._frames = []

    def add_frame(self, frame: bytes) -> None:
        if self.recording and frame:
            self._frames.append(frame)

    def key_up(self) -> bytes | None:
        if not self.recording:
            return None
        self.recording = False
        audio = b"".join(self._frames)
        self._frames = []
        return audio or None
