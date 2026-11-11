import type { Benchmark } from "@/api";
import { otherSummary, personalSummary } from "@/copy";
import { Note, TipList } from "@/ui";

export function LapReport({ benchmark }: { benchmark: Benchmark }) {
  return (
    <>
      <h2>Your laps</h2>
      <p>{personalSummary(benchmark.personal)}</p>
      <TipList tips={benchmark.personal.tips} />
      <h2>Other drivers</h2>
      <p>{otherSummary(benchmark.others)}</p>
      <TipList tips={benchmark.others.tips} />
      {benchmark.others.board.length ? (
        <ul className="board">
          {benchmark.others.board.map((row) => (
            <li key={`${row.driver_name}-${row.lap_time_s}`}>
              <span>{row.driver_name}</span>
              <p>{row.lap_time_s.toFixed(3)} s</p>
            </li>
          ))}
        </ul>
      ) : null}
      <h2>Pro file</h2>
      {benchmark.pro.available ? null : <p>{benchmark.pro.spoken_text}</p>}
      <TipList tips={benchmark.pro.tips} />
      <h2>Grip</h2>
      {benchmark.grip.length ? (
        benchmark.grip.map((flag) => <p key={flag.spoken_text}>{flag.spoken_text}</p>)
      ) : (
        <Note>No wheel slip or tyres off the track were recorded.</Note>
      )}
    </>
  );
}
