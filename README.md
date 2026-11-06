# Assetto Corsa Coach

A local driving coach for the original Assetto Corsa. The gaming PC reads the game's shared memory and sends a versioned telemetry stream to an AI host. The host records the session, compares laps, and answers from that evidence.

The gaming PC and the AI host are separate. The agent's backend address is a setting, so the host can later move off the Mac without a code change.

## What works in this build

- A versioned telemetry message, with units documented in [docs/telemetry-protocol.md](docs/telemetry-protocol.md).
- The Windows shared-memory reader, tested here against the in-game page layout and a sample page. It has not yet been compared with a live session on your PC.
- Recording, replay, lap comparison, and coaching rules. Corner advice needs a calibrated track file. The only calibrated file shipped here is the synthetic test track.
- A dashboard for live values, laps, coaching, and text questions.
- Text answers from the recorded numbers. Until Ollama is configured, a deterministic explainer answers. A reply that contains a number missing from the evidence is discarded.
- Push-to-talk state on the agent, and an audio socket on the host. Speech-to-text and speech synthesis are not bundled. The audio socket says so instead of pretending to hear you.

## What this build does not do yet

- Confirm speed, rpm, gear, pedals, lap count, and track position against the game on your monitor.
- Compile the Windows installer. The PyInstaller spec and Inno Setup script are in `apps/windows-agent/packaging/`.
- Benchmark a local model, speech recognition, or speech synthesis on the 24 GB Mac.
- Support Assetto Corsa Competizione, setup advice, or wake-word activation.

Install and run it with [INSTALL.md](INSTALL.md). The engineering notes live in [llm-wiki/index.md](llm-wiki/index.md).
