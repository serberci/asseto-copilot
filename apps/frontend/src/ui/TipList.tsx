import type { ComparisonTip } from "@/api";
import { adviceLabel } from "@/copy";
import { Badge } from "./Badge";

export function TipList({ tips }: { tips: ComparisonTip[] }) {
  if (!tips.length) return null;
  return (
    <div className="tips">
      {tips.map((tip) => {
        const label = adviceLabel(tip.recommendation_allowed);
        return (
          <p key={tip.spoken_text}>
            <Badge tone={label}>{label}</Badge> {tip.spoken_text}
          </p>
        );
      })}
    </div>
  );
}
