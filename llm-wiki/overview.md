# Overview

Assetto Corsa Coach is a two-computer system for the original game.

The Windows agent reads `acpmf_physics`, `acpmf_graphics`, and `acpmf_static`, normalizes one sample, and publishes it on a WebSocket. The Mac host stores the sample, closes laps, compares a lap with a reference, and answers questions from those numbers.

The product name in the window and the dashboard is Assetto Corsa Coach. The Windows program is the Assetto Corsa Coach Agent.

This tree was empty except for `PLAN.md` and `context.txt`. The implementation follows that plan through a testable host and a Windows telemetry core. It does not pretend the live game, the installer, or the speech engines have been run.

Python packages:

| Package | Path | Role |
|---|---|---|
| `telemetry-schema` | `packages/telemetry-schema` | Messages both sides validate |
| `coach-agent` | `apps/windows-agent` | Reader, publisher, tray app |
| `coach-backend` | `apps/backend` | Host |
| dashboard | `apps/frontend` | React page served by the host after `npm run build` |

`fixtures/synthetic-session.jsonl` is the stand-in for a recorded session. `fixtures/page-sample.json` is the stand-in for shared memory.
