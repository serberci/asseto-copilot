import type { ReactNode } from "react";

export function Answer({ note, children }: { note?: ReactNode; children: ReactNode }) {
  return (
    <p className="answer">
      {children}
      {note != null ? <span>{note}</span> : null}
    </p>
  );
}
