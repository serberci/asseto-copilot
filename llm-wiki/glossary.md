# Glossary

| Term | Meaning |
|---|---|
| Agent | The Windows program. Process `acs.exe` is the game, not the agent. |
| Host | The FastAPI process. First on the Mac, later maybe a VPS. The agent only knows its URL. |
| Page | One shared-memory struct: physics, graphics, or static. |
| Sample | One normalized telemetry payload. |
| Stale | The page's `packetId` did not change since the previous read. |
| Progress | `normalizedCarPosition`, 0 at the start line and 1 as the car approaches it again. |
| Reference lap | The valid lap a comparison uses. Fastest other valid lap, unless the driver picks one. |
| Calibrated track | A JSON file with `calibrated: true` and corner progress that a person checked. |
| Observation | A coaching result that must not be spoken as advice. |
| Explainer | The default answerer. It fills a sentence from the context. It is not a language model. |
| Layout confirmed | An empty file `layout-confirmed` in the agent settings directory, written by the user after the live check. |
