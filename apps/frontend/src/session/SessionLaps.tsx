import type { Lap, Telemetry } from "@/api";
import { lapState } from "@/copy";
import { lapTime } from "@/format";
import { Panel, Table } from "@/ui";

export function SessionLaps({
  laps,
  referenceLapId,
  telemetry,
  onChooseReference,
}: {
  laps: Lap[];
  referenceLapId: string | null;
  telemetry: Telemetry | null | undefined;
  onChooseReference: (lap: Lap) => Promise<void>;
}) {
  return (
    <Panel title="Laps">
      <Table headers={["Lap", "Time", "State", ""]}>
        {laps.map((lap) => (
          <tr key={lap.id}>
            <td>{lap.lap_number}</td>
            <td>{lapTime(lap.lap_time_ms)}</td>
            <td>{lapState(lap.valid, lap.invalid_reasons)}</td>
            <td>
              {lap.valid ? (
                <button type="button" onClick={() => void onChooseReference(lap)}>
                  {referenceLapId === lap.id ? "Reference" : "Use as reference"}
                </button>
              ) : null}
            </td>
          </tr>
        ))}
      </Table>
      <p className="times">
        Current {lapTime(telemetry?.current_lap_time_ms)} · last {lapTime(telemetry?.last_lap_time_ms)} · best{" "}
        {lapTime(telemetry?.best_lap_time_ms)}
      </p>
    </Panel>
  );
}
