import { useCallback, useEffect, useState } from "react";
import { getBenchmark, listLaps, type Benchmark, type CatalogLap } from "@/api";
import { lapState } from "@/copy";
import { lapTime } from "@/format";
import { ErrorText, Note, Section, Table, TrackSelect, errorMessage } from "@/ui";
import { LapDrawer } from "./LapDrawer";

export function LapsPage() {
  const [laps, setLaps] = useState<CatalogLap[]>([]);
  const [track, setTrack] = useState("");
  const [selected, setSelected] = useState<CatalogLap | null>(null);
  const [benchmark, setBenchmark] = useState<Benchmark | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const close = useCallback(() => setSelected(null), []);

  useEffect(() => {
    listLaps()
      .then((body) => setLaps(body.laps))
      .catch((reason: unknown) => setError(errorMessage(reason, "The laps could not be loaded.")));
  }, []);

  const tracks = [...new Set(laps.map((lap) => lap.track_id))];
  const shown = track ? laps.filter((lap) => lap.track_id === track) : laps;

  async function openLap(lap: CatalogLap) {
    setSelected(lap);
    setBenchmark(null);
    setDetailError(null);
    try {
      setBenchmark(await getBenchmark(lap.id));
    } catch (reason) {
      setDetailError(errorMessage(reason, "The lap was not found."));
    }
  }

  return (
    <Section title="Laps">
      <TrackSelect tracks={tracks} value={track} onChange={setTrack} allLabel="All tracks" />
      <ErrorText>{error}</ErrorText>
      <Table headers={["Track", "Car", "Lap", "Time", "State", ""]}>
        {shown.map((lap) => (
          <tr key={lap.id}>
            <td>{lap.track_id}</td>
            <td>{lap.car_model}</td>
            <td>{lap.lap_number}</td>
            <td>{lapTime(lap.lap_time_ms)}</td>
            <td>{lapState(lap.valid, lap.invalid_reasons)}</td>
            <td>
              <button type="button" onClick={() => void openLap(lap)}>
                Details
              </button>
            </td>
          </tr>
        ))}
      </Table>
      {shown.length === 0 ? <Note>No laps for this track.</Note> : null}
      {selected ? <LapDrawer lap={selected} benchmark={benchmark} detailError={detailError} onClose={close} /> : null}
    </Section>
  );
}
