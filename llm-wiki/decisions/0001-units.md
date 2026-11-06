# 0001 — Units, and steering left unnamed

Speed on the wire is meters per second because `speedKmh / 3.6` is exact and the dashboard can show km/h without a second speed field. Gear follows the game: 0 reverse, 1 neutral, 2 first.

Pedals are 0 to 1. A reading outside −0.05 to 1.05 is treated as a layout failure and is not published.

`steering` is the raw `steerAngle`. The field is expected to be radians, but that was not confirmed on a live car in this implementation. Naming it `steering_angle_rad` would make a wrong unit look official. The first diagnose must check the magnitude. See [../../docs/validation.md](../../docs/validation.md).

Fuel is stored as `fuel_l` and tyre temperatures as Celsius because that is what the in-game readouts use in the layouts we followed. Both still need the first session to confirm the number, not just the name.
