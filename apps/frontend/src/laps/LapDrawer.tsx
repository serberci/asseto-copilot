import type { Benchmark, CatalogLap } from "@/api";
import { formatTimestamp } from "@/copy";
import { lapTime } from "@/format";
import { Drawer, ErrorText, Facts, Note } from "@/ui";
import { LapReport } from "./LapReport";

export function LapDrawer({
  lap,
  benchmark,
  detailError,
  onClose,
}: {
  lap: CatalogLap;
  benchmark: Benchmark | null;
  detailError: string | null;
  onClose: () => void;
}) {
  return (
    <Drawer
      label={`Lap ${lap.lap_number} on ${lap.track_id}`}
      eyebrow={lap.track_id}
      title={
        <>
          Lap {lap.lap_number} · {lapTime(lap.lap_time_ms)}
        </>
      }
      onClose={onClose}
    >
      <Facts
        rows={[
          { label: "Car", value: lap.car_model },
          { label: "Game", value: lap.game },
          { label: "Driver", value: lap.driver_name ?? "Unassigned" },
          { label: "Started", value: formatTimestamp(lap.started_at) },
          { label: "State", value: lap.valid ? "Valid" : lap.invalid_reasons.join(", ") || "Invalid" },
        ]}
      />
      <ErrorText>{detailError}</ErrorText>
      {benchmark ? <LapReport benchmark={benchmark} /> : detailError ? null : <Note>Loading this lap.</Note>}
    </Drawer>
  );
}
