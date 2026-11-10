# 0006 — Pro laps are files we are allowed to keep

A published Competizione trace can show brake, throttle, gear, and steering for one car and one track. The laps on ACCReplay belong to the drivers who uploaded them and to that site. They are not copied into this repository.

The bundled McLaren files under `coach_backend/track_data/references/` are synthetic. `source` is `synthetic-test`. The progress values are not Spa corners. A pro file is used only when the game, track, and car all match. A Ferrari lap in the original game is not compared with the McLaren file.

Personal history is every valid lap already stored for that same driver, game, track, and car. The driver can still pin one lap as the reference. Steering peaks and raw wheel slip are recorded. They are not spoken as a change to make. A brake tip is spoken only when entry speed matches and the lap lost time by braking earlier than the reference.
