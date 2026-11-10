# Glossary

| Term | Meaning |
|---|---|
| Agent | The Windows program. Process `acs.exe` is the game, not the agent. |
| Host | The FastAPI process. First on the Mac, later maybe a VPS. The agent only knows its URL. |
| Page | One shared-memory struct: physics, graphics, or static. |
| Sample | One normalized telemetry payload. |
| Stale | The page's `packetId` did not change since the previous read. |
| Progress | `normalizedCarPosition`, 0 at the start line and 1 as the car approaches it again. |
| Administrator | The account that creates drivers. The first password is written to `data/admin.password`. The host token can still call the API as the administrator. |
| Driver | An account with a name and a password for the dashboard, and a separate agent token for the Windows agent. Sessions and laps belong to that driver. |
| Reference lap | The valid lap a comparison uses. For one driver, the fastest other valid lap of that same driver, unless they pick one. Other drivers and pro files are separate comparisons. |
| Calibrated track | A JSON file with `calibrated: true` and corner progress that a person checked. |
| Observation | A coaching result that must not be spoken as advice. |
| Explainer | The default answerer. It fills a sentence from the context. It is not a language model. |
| Layout confirmed | An empty file `layout-confirmed` in the agent settings directory, written by the user after the live check. |
