"""Windows file-mapping lifecycle for the three Assetto Corsa pages.

The reader copies bytes out of the view. It does not keep a ctypes object
pointing at live shared memory.
"""

from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes
from dataclasses import dataclass

from coach_agent.core.layouts import GRAPHICS_BYTES, GRAPHICS_NAME, PHYSICS_BYTES, PHYSICS_NAME, STATIC_BYTES, STATIC_NAME

FILE_MAP_READ = 0x0004


class SharedMemoryUnavailable(RuntimeError):
    """Assetto Corsa is not exposing the named mapping yet."""


@dataclass
class _View:
    handle: int
    pointer: int
    size: int

    def read(self) -> bytes:
        return ctypes.string_at(self.pointer, self.size)

    def close(self) -> None:
        if self.pointer:
            ctypes.windll.kernel32.UnmapViewOfFile(self.pointer)
            self.pointer = 0
        if self.handle:
            ctypes.windll.kernel32.CloseHandle(self.handle)
            self.handle = 0


def _open_view(name: str, size: int) -> _View:
    if sys.platform != "win32":
        raise SharedMemoryUnavailable(f"{name} is only available on Windows while Assetto Corsa is running")
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenFileMappingW.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR]
    kernel32.OpenFileMappingW.restype = wintypes.HANDLE
    kernel32.MapViewOfFile.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.c_size_t,
    ]
    kernel32.MapViewOfFile.restype = ctypes.c_void_p
    kernel32.UnmapViewOfFile.argtypes = [ctypes.c_void_p]
    kernel32.UnmapViewOfFile.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL

    handle = kernel32.OpenFileMappingW(FILE_MAP_READ, False, name)
    if not handle:
        error = ctypes.get_last_error()
        raise SharedMemoryUnavailable(f"OpenFileMappingW({name}) failed (winerror {error})")
    pointer = kernel32.MapViewOfFile(handle, FILE_MAP_READ, 0, 0, size)
    if not pointer:
        error = ctypes.get_last_error()
        kernel32.CloseHandle(handle)
        raise SharedMemoryUnavailable(f"MapViewOfFile({name}) failed (winerror {error})")
    return _View(handle=int(handle), pointer=int(pointer), size=size)


class WindowsSharedMemory:
    """Opens `acpmf_physics`, `acpmf_graphics`, and `acpmf_static`."""

    def __init__(self) -> None:
        self._physics = _open_view(PHYSICS_NAME, PHYSICS_BYTES)
        try:
            self._graphics = _open_view(GRAPHICS_NAME, GRAPHICS_BYTES)
            self._static = _open_view(STATIC_NAME, STATIC_BYTES)
        except Exception:
            self.close()
            raise

    def read_physics(self) -> bytes:
        return self._physics.read()

    def read_graphics(self) -> bytes:
        return self._graphics.read()

    def read_static(self) -> bytes:
        return self._static.read()

    def close(self) -> None:
        for view in (getattr(self, "_physics", None), getattr(self, "_graphics", None), getattr(self, "_static", None)):
            if view is not None:
                view.close()


class BufferSharedMemory:
    """Test double that serves fixed page images."""

    def __init__(self, physics: bytes, graphics: bytes, static: bytes) -> None:
        self.physics = physics
        self.graphics = graphics
        self.static = static
        self.closed = False

    def read_physics(self) -> bytes:
        self._check()
        return self.physics

    def read_graphics(self) -> bytes:
        self._check()
        return self.graphics

    def read_static(self) -> bytes:
        self._check()
        return self.static

    def close(self) -> None:
        self.closed = True

    def _check(self) -> None:
        if self.closed:
            raise SharedMemoryUnavailable("shared memory is closed")
