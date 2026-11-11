import type { Coaching } from "@/api";
import { CoachingLine, Note, Panel } from "@/ui";

export function CoachingList({ events }: { events: Coaching[] }) {
  return (
    <Panel title="Coaching">
      <ul>
        {events.map((event) => (
          <li key={event.id}>
            <CoachingLine event={event} />
          </li>
        ))}
      </ul>
      {events.length === 0 ? <Note>No coaching events for this session.</Note> : null}
    </Panel>
  );
}
