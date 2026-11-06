# Validation still required on the gaming PC

The layout sizes and field offsets match the in-game Python shared-memory definition, and a byte image of those pages round-trips through the reader. That is not the same as a live car.

With Assetto Corsa running, `coach-agent --diagnose` must agree with the screen on all of these before `layout-confirmed` is created:

- Speed, against the game's km/h readout. The protocol stores m/s. Diagnose prints `speedKmh`.
- RPM and gear. Reverse, neutral, and first must match gear 0, 1, and 2.
- Throttle and brake at rest and at full pedal.
- Lap counter and normalized position around one lap. Position should move from near 0 to near 1 and wrap at the line.
- Track name and car folder name.
- Steering magnitude. If the printed `steer` is tens or hundreds at a modest wheel angle, the field is not in radians and coaching must not use it until the protocol is corrected.

Also record thirty seconds with `--record` and check that repeated packet ids are marked stale in the JSONL rather than stored as new motion.

The Windows installer has not been compiled in this environment. Build it on a clean Windows machine after the checks above.
