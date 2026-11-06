# 0004 — The model does not see the database

Lap time, delta, and corner metrics are computed in `coach_backend.analysis` and `coach_backend.coaching`. The language model is optional.

`Store.context` builds the only object the model is given: session identity, latest valid lap, best lap, lap delta, and recent coaching. Those are the controlled lookups from the plan (`get_current_session`, `get_current_lap`, `get_current_lap_delta`, `get_best_lap`, `get_recent_coaching_events`). They are called by the host before the prompt, not offered to the model as free tools, so a reply cannot query past them.

`COACH_OLLAMA_HOST` empty means the deterministic explainer answers. The model name `llama3.2:3b` is only the default string for the day someone points the host at Ollama. It has not been benchmarked on the 24 GB machine.

Every spoken number must already appear in that context (`is_grounded`). The model's own evidence object is ignored and replaced with the host context. If the check fails, the explainer's sentence is what the driver sees and the model field is `rejected-ungrounded`.

Speech engines are the same kind of boundary. `answer_audio` returns `stt_unavailable` until a transcriber is configured. None is configured.
