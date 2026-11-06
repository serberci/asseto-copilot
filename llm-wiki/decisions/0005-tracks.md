# 0005 — Track files are not guessed

Normalized progress does not know where a corner is. Corner metrics run only when `TrackLibrary.get` finds a file whose `track_id` matches the session and whose `calibrated` flag is true.

The bundled `synthetic-oval` file exists so the tests and the replayed fixture have one corner, Turn 1, from progress 0.40 to 0.60. It is not a circuit.

`_template.json` is not listed and is not loaded. A real track is a copy in `data/tracks/<track-id>.json` with progress values taken from a recorded lap. A corner that wraps across the start line is rejected by the model because entry, apex, and exit must increase. That case needs an explicit representation later, not a guessed pair of numbers.

User files are checked first. An uncalibrated user file with the same track id hides the bundled file: lookup stops and returns nothing, it does not fall through.
