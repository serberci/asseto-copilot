# Log

## 2026-11-06

Started from `PLAN.md` and `context.txt` in an otherwise empty repository.

Built protocol 1.0.0, the Windows reader, the host, the dashboard, and the tests that can run on macOS. 23 pytest tests passed on Python 3.14. The dashboard production build succeeded. A replayed synthetic session was opened in the browser: 180 km/h, gear 3, both lap times, the +0.400 delta, the four coaching lines, a grounded answer, and a reference-lap change.

Not done, because this machine is not the gaming PC and no model was benchmarked:

- Live shared-memory comparison. See [../docs/validation.md](../docs/validation.md).
- A compiled installer. The GitHub Actions workflow can build it on a Windows runner. The shared-memory layout is still unchecked against a live session.
- Ollama, faster-whisper, Piper, or any substitute. The audio socket returns `stt_unavailable`. The text path uses the explainer unless `COACH_OLLAMA_HOST` is set.
- A real track file. `synthetic-oval` is the only calibrated track, and it is fake.
- A real pro trace. The McLaren files in `track_data/references/` are synthetic test data, not an ACCReplay download.

The next human step is the live diagnose on Windows, then a real track file for one car and one circuit.
