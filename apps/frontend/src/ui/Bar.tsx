import { pedalWidth } from "@/format";

export function Bar({ label, value, kind }: { label: string; value: number | undefined; kind: "throttle" | "brake" }) {
  return (
    <div className="bar">
      <span>{label}</span>
      <div>
        <i className={kind} style={{ width: pedalWidth(value) }} />
      </div>
    </div>
  );
}
