# 0002 — Shared-memory layout

The pages are the in-game Python layout shipped as `sim_info.py` in Custom Shaders Patch `AccExtHelper` (the Rombik layout Assetto Corsa apps use). Field order was also checked against `mdjarv/assettocorsasharedmemory` through physics `localVelocity` and graphics `mandatoryPitDone`.

Two disagreements, resolved in favor of the in-game Python file:

- `trackConfiguration` is 33 UTF-16 code units there. mdjarv declares 15. A 15-wide field would shift `carSkin` and the pit window.
- Graphics includes `windSpeed` and `windDirection`. The older C# struct stops at `mandatoryPitDone`.

Text is stored as UTF-16 code units, not the host `wchar_t`. On macOS `c_wchar` is 4 bytes and would make every later field wrong. The structs use MSVC packing (`_pack_ = 4`, and `_layout_ = "ms"` on Python 3.14+).

Measured sizes of this prefix:

| Page | Bytes |
|---|---|
| Physics | 580 |
| Graphics | 296 |
| Static | 684 |

The game mapping may be longer. Extra bytes are ignored. A shorter mapping fails the read. Offsets locked by tests include `speedKmh` at 28, `gear` at 16, `completedLaps` at 132, `normalizedCarPosition` at 248, `carModel` at 68, and `track` at 134.

Windows opens the names `acpmf_physics`, `acpmf_graphics`, and `acpmf_static` with `OpenFileMappingW` and `MapViewOfFile`, copies the bytes out, and unmaps. The reader does not keep a ctypes object on the live view.

This is the layout contract. It is not yet a live-session confirmation.
