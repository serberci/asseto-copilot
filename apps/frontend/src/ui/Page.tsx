import type { ReactNode } from "react";

export function Page({ children }: { children: ReactNode }) {
  return <main>{children}</main>;
}
