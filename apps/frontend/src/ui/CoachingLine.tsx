import type { Coaching } from "@/api";
import { coachingLabel } from "@/copy";
import { Badge } from "./Badge";

export function CoachingLine({ event }: { event: Coaching }) {
  const label = coachingLabel(event.delivered_at, event.recommendation_allowed);
  return (
    <>
      <Badge tone={label}>{label}</Badge>
      <p>{event.spoken_text}</p>
    </>
  );
}
