import { useEffect, useState } from "react";
import { getPerformance, listLaps, type PerformancePoint } from "@/api";
import { changeLabel } from "@/copy";
import { ErrorText, Note, Section, Table, TrackSelect, errorMessage } from "@/ui";

export function PerformancePage() {
  const [tracks, setTracks] = useState<string[]>([]);
  const [track, setTrack] = useState("");
  const [points, setPoints] = useState<PerformancePoint[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listLaps()
      .then((body) => {
        const names = [...new Set(body.laps.map((lap) => lap.track_id))];
        setTracks(names);
        setTrack((current) => current || names[0] || "");
      })
      .catch((reason: unknown) => setError(errorMessage(reason, "The tracks could not be loaded.")));
  }, []);

  useEffect(() => {
    if (!track) return;
    getPerformance(track)
      .then((body) => setPoints(body.laps))
      .catch((reason: unknown) => setError(errorMessage(reason, "The performance could not be loaded.")));
  }, [track]);

  return (
    <Section title="Performance">
      <TrackSelect tracks={tracks} value={track} onChange={setTrack} />
      <ErrorText>{error}</ErrorText>
      {points.length === 0 ? <Note>No valid laps on this track.</Note> : null}
      <Table headers={["Time", "Change"]}>
        {points.map((point) => (
          <tr key={point.lap_id}>
            <td>{point.lap_time_s.toFixed(3)} s</td>
            <td>{changeLabel(point.improvement_s)}</td>
          </tr>
        ))}
      </Table>
    </Section>
  );
}
