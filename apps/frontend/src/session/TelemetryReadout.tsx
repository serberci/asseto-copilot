import type { Telemetry } from "@/api";
import { kmh, signedSeconds } from "@/format";
import { Bar, Section, Stat } from "@/ui";

export function TelemetryReadout({
  telemetry,
  analysisLoss,
}: {
  telemetry: Telemetry | null | undefined;
  analysisLoss: number | null;
}) {
  return (
    <>
      <Section className="readout">
        <Stat label="Speed" value={kmh(telemetry?.speed_mps)} detail="km/h" />
        <Stat label="Gear" value={telemetry?.gear ?? "—"} detail={telemetry?.session_status ?? "waiting"} />
        <Stat label="RPM" value={telemetry ? telemetry.rpm : "—"} detail={`lap ${telemetry?.lap_number ?? "—"}`} />
        <Stat label="Delta" value={signedSeconds(analysisLoss)} detail="vs your reference" />
      </Section>
      <Section className="pedals">
        <Bar label="Throttle" value={telemetry?.throttle} kind="throttle" />
        <Bar label="Brake" value={telemetry?.brake} kind="brake" />
        <p>
          Steering {telemetry ? telemetry.steering.toFixed(3) : "—"} · progress{" "}
          {telemetry ? `${Math.round(telemetry.normalized_progress * 100)}%` : "—"}
        </p>
      </Section>
    </>
  );
}
