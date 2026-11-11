import type { ReactNode } from "react";

export function Stat({ label, value, detail }: { label: string; value: ReactNode; detail: ReactNode }) {
  return (
    <div>
      <span>{label}</span>
      <strong>{value}</strong>
      <em>{detail}</em>
    </div>
  );
}
