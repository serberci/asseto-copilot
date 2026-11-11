import { dashboardStatus } from "@/copy";
import { ErrorText, Note, Section, Status } from "@/ui";
import { AskPanel } from "./AskPanel";
import { CoachingList } from "./CoachingList";
import { SessionLaps } from "./SessionLaps";
import { TelemetryReadout } from "./TelemetryReadout";
import { useLiveDashboard } from "./useLiveDashboard";

export function CurrentSession() {
  const dashboard = useLiveDashboard();
  const session = dashboard.live?.session ?? null;

  return (
    <Section>
      <Status on={dashboard.connected}>
        {dashboardStatus(dashboard.connected, dashboard.live?.connected_agents ?? 0, session)}
      </Status>
      <ErrorText>{dashboard.error}</ErrorText>
      {!session ? <Note>No session yet. Start the Windows agent with this driver's token.</Note> : null}
      <TelemetryReadout telemetry={dashboard.live?.telemetry} analysisLoss={dashboard.analysisLoss} />
      <Section className="split">
        <SessionLaps
          laps={dashboard.live?.laps ?? []}
          referenceLapId={session?.reference_lap_id ?? null}
          telemetry={dashboard.live?.telemetry}
          onChooseReference={dashboard.chooseReference}
        />
        <CoachingList events={dashboard.live?.coaching ?? []} />
      </Section>
      <AskPanel sessionId={session?.id ?? null} onError={dashboard.setError} />
    </Section>
  );
}
