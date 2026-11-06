# Architecture

The gaming PC and the AI host share one versioned message and nothing else.

```text
Assetto Corsa shared memory
        │
        ▼
Windows agent
  read physics and graphics pages
  normalize
  ring buffer and JSONL
  WebSocket  /ws/telemetry
        │
        ▼
FastAPI host
  SQLite for sessions, laps, coaching, conversation
  Parquet for samples
  lap comparison and coaching rules
  explainer or Ollama
  /ws/dashboard  /ws/audio  /api/v1
        │
        ▼
Dashboard in the gaming PC browser
```

The agent never asks the model to interpret a sample. The model, when it is enabled, receives a small context built by named lookups: the current session, the current lap, the lap delta, the best lap, and recent coaching. It does not receive the database or the raw stream.

Speech, when a local engine is configured later, is a second path. The telemetry socket does not wait for it.

Shared-memory pages are read with `OpenFileMappingW`, `MapViewOfFile`, `UnmapViewOfFile`, and `CloseHandle` on Windows. Tests use a byte image of the same pages. The field order is the in-game Python layout, recorded in [telemetry-protocol.md](telemetry-protocol.md) and [../llm-wiki/decisions/0002-shared-memory-layout.md](../llm-wiki/decisions/0002-shared-memory-layout.md).

The agent UI is a thin window over that core. Closing it hides the window. The process stays in the signed-in user session because the headset belongs to that session. It is not a Windows service.

The host is one FastAPI process. Docker can run that process. It does not run Ollama or the speech engines.
