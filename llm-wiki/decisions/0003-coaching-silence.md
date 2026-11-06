# 0003 — Coaching may stay silent

A comparison can be true and still be a bad thing to say.

Entry speed must be within 3% and the car and track must match before a brake, coast, throttle, or exit-speed event is allowed as a recommendation. If entry speed differs, the only brake event is `advice: none` with `recommendation_allowed: false`. The sentence says the laps are not comparable. It does not tell the driver to brake later.

Braking later than the reference is recorded as `braked_later_than_reference` and is also not a recommendation. Being later than the reference is not a reason to brake later still.

The scheduler drops events that are not recommendations. It also waits while brake is 0.15 or more, while throttle is below 0.5, or while progress is inside a calibrated corner. The same dedup key waits 20 seconds.

Uncertainty remains on the dashboard as an observation. Not every true measurement is spoken.
