import type { ReactNode } from "react";

export function Note({ children }: { children: ReactNode }) {
  return <p className="empty">{children}</p>;
}

export function ErrorText({ children }: { children: ReactNode }) {
  if (children == null || children === false || children === "") return null;
  return <p className="error">{children}</p>;
}

export function Status({ on, children }: { on: boolean; children: ReactNode }) {
  return <p className={on ? "status on" : "status"}>{children}</p>;
}
