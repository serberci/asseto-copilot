"""Original Assetto Corsa shared-memory pages.

Field order follows the in-game Python layout used by Assetto Corsa apps
(the Rombik `sim_info.py` carried in Custom Shaders Patch AccExtHelper),
cross-checked against mdjarv/assettocorsasharedmemory through `localVelocity`
and `mandatoryPitDone`.

`trackConfiguration` is 33 UTF-16 code units in the in-game layout. mdjarv
declares 15; this module follows the in-game layout. Graphics includes
`windSpeed` and `windDirection`, which that layout has and the older C#
struct does not.

Windows `wchar_t` is 2 bytes. Host `c_wchar` is 4 bytes on macOS, so text
fields are stored as UTF-16 code units. `_pack_ = 4` matches the MSVC layout
the game is built with. Bytes the game writes after this prefix are ignored.
A live session still has to confirm the values before they are trusted.
"""

from __future__ import annotations

import sys
import ctypes
from ctypes import c_float, c_int32, c_uint16
from datetime import datetime

PHYSICS_BYTES = 580
GRAPHICS_BYTES = 296
STATIC_BYTES = 684

PHYSICS_NAME = "acpmf_physics"
GRAPHICS_NAME = "acpmf_graphics"
STATIC_NAME = "acpmf_static"


def _structure(name: str, fields: list[tuple[str, type]]) -> type[ctypes.Structure]:
    namespace: dict = {"_pack_": 4, "_fields_": fields}
    if sys.version_info >= (3, 14):
        namespace["_layout_"] = "ms"
    return type(name, (ctypes.Structure,), namespace)


def _f(count: int) -> type:
    return c_float * count


def _w(count: int) -> type:
    return c_uint16 * count


PhysicsPage = _structure(
    "PhysicsPage",
    [
        ("packetId", c_int32),
        ("gas", c_float),
        ("brake", c_float),
        ("fuel", c_float),
        ("gear", c_int32),
        ("rpms", c_int32),
        ("steerAngle", c_float),
        ("speedKmh", c_float),
        ("velocity", _f(3)),
        ("accG", _f(3)),
        ("wheelSlip", _f(4)),
        ("wheelLoad", _f(4)),
        ("wheelsPressure", _f(4)),
        ("wheelAngularSpeed", _f(4)),
        ("tyreWear", _f(4)),
        ("tyreDirtyLevel", _f(4)),
        ("tyreCoreTemperature", _f(4)),
        ("camberRAD", _f(4)),
        ("suspensionTravel", _f(4)),
        ("drs", c_float),
        ("tc", c_float),
        ("heading", c_float),
        ("pitch", c_float),
        ("roll", c_float),
        ("cgHeight", c_float),
        ("carDamage", _f(5)),
        ("numberOfTyresOut", c_int32),
        ("pitLimiterOn", c_int32),
        ("abs", c_float),
        ("kersCharge", c_float),
        ("kersInput", c_float),
        ("autoShifterOn", c_int32),
        ("rideHeight", _f(2)),
        ("turboBoost", c_float),
        ("ballast", c_float),
        ("airDensity", c_float),
        ("airTemp", c_float),
        ("roadTemp", c_float),
        ("localAngularVel", _f(3)),
        ("finalFF", c_float),
        ("performanceMeter", c_float),
        ("engineBrake", c_int32),
        ("ersRecoveryLevel", c_int32),
        ("ersPowerLevel", c_int32),
        ("ersHeatCharging", c_int32),
        ("ersIsCharging", c_int32),
        ("kersCurrentKJ", c_float),
        ("drsAvailable", c_int32),
        ("drsEnabled", c_int32),
        ("brakeTemp", _f(4)),
        ("clutch", c_float),
        ("tyreTempI", _f(4)),
        ("tyreTempM", _f(4)),
        ("tyreTempO", _f(4)),
        ("isAIControlled", c_int32),
        ("tyreContactPoint", _f(12)),
        ("tyreContactNormal", _f(12)),
        ("tyreContactHeading", _f(12)),
        ("brakeBias", c_float),
        ("localVelocity", _f(3)),
    ],
)

GraphicsPage = _structure(
    "GraphicsPage",
    [
        ("packetId", c_int32),
        ("status", c_int32),
        ("session", c_int32),
        ("currentTime", _w(15)),
        ("lastTime", _w(15)),
        ("bestTime", _w(15)),
        ("split", _w(15)),
        ("completedLaps", c_int32),
        ("position", c_int32),
        ("iCurrentTime", c_int32),
        ("iLastTime", c_int32),
        ("iBestTime", c_int32),
        ("sessionTimeLeft", c_float),
        ("distanceTraveled", c_float),
        ("isInPit", c_int32),
        ("currentSectorIndex", c_int32),
        ("lastSectorTime", c_int32),
        ("numberOfLaps", c_int32),
        ("tyreCompound", _w(33)),
        ("replayTimeMultiplier", c_float),
        ("normalizedCarPosition", c_float),
        ("carCoordinates", _f(3)),
        ("penaltyTime", c_float),
        ("flag", c_int32),
        ("idealLineOn", c_int32),
        ("isInPitLine", c_int32),
        ("surfaceGrip", c_float),
        ("mandatoryPitDone", c_int32),
        ("windSpeed", c_float),
        ("windDirection", c_float),
    ],
)

StaticPage = _structure(
    "StaticPage",
    [
        ("smVersion", _w(15)),
        ("acVersion", _w(15)),
        ("numberOfSessions", c_int32),
        ("numCars", c_int32),
        ("carModel", _w(33)),
        ("track", _w(33)),
        ("playerName", _w(33)),
        ("playerSurname", _w(33)),
        ("playerNick", _w(33)),
        ("sectorCount", c_int32),
        ("maxTorque", c_float),
        ("maxPower", c_float),
        ("maxRpm", c_int32),
        ("maxFuel", c_float),
        ("suspensionMaxTravel", _f(4)),
        ("tyreRadius", _f(4)),
        ("maxTurboBoost", c_float),
        ("airTemp", c_float),
        ("roadTemp", c_float),
        ("penaltiesEnabled", c_int32),
        ("aidFuelRate", c_float),
        ("aidTireRate", c_float),
        ("aidMechanicalDamage", c_float),
        ("aidAllowTyreBlankets", c_int32),
        ("aidStability", c_float),
        ("aidAutoClutch", c_int32),
        ("aidAutoBlip", c_int32),
        ("hasDRS", c_int32),
        ("hasERS", c_int32),
        ("hasKERS", c_int32),
        ("kersMaxJ", c_float),
        ("engineBrakeSettingsCount", c_int32),
        ("ersPowerControllerCount", c_int32),
        ("trackSPlineLength", c_float),
        ("trackConfiguration", _w(33)),
        ("ersMaxJ", c_float),
        ("isTimedRace", c_int32),
        ("hasExtraLap", c_int32),
        ("carSkin", _w(33)),
        ("reversedGridPositions", c_int32),
        ("pitWindowStart", c_int32),
        ("pitWindowEnd", c_int32),
    ],
)


class SharedMemoryError(RuntimeError):
    """The mapped bytes could not be read as an Assetto Corsa page."""


def decode_text(units) -> str:
    characters: list[str] = []
    for code in units:
        if code == 0:
            break
        characters.append(chr(int(code)))
    return "".join(characters)


def _load(page_type: type[ctypes.Structure], blob: bytes) -> ctypes.Structure:
    size = ctypes.sizeof(page_type)
    if len(blob) < size:
        raise SharedMemoryError(f"{page_type.__name__} needs {size} bytes, got {len(blob)}")
    return page_type.from_buffer_copy(blob[:size])


def read_physics_page(blob: bytes) -> ctypes.Structure:
    return _load(PhysicsPage, blob)


def read_graphics_page(blob: bytes) -> ctypes.Structure:
    return _load(GraphicsPage, blob)


def read_static_page(blob: bytes) -> ctypes.Structure:
    return _load(StaticPage, blob)


def page_bytes(page: ctypes.Structure) -> bytes:
    return bytes(page)


def stamp(read_at: datetime) -> datetime:
    if read_at.tzinfo is None:
        raise SharedMemoryError("shared-memory reads must be stamped with a timezone-aware clock")
    return read_at
