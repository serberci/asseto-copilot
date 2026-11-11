import type { ReactNode } from "react";

export function BrandHeader({ children }: { children?: ReactNode }) {
  return (
    <header>
      <div>
        <p className="eyebrow">Pit wall</p>
        <h1>Assetto Corsa Coach</h1>
      </div>
      {children}
    </header>
  );
}
