import type { ReactNode } from "react";

export function Section({
  title,
  className,
  children,
}: {
  title?: string;
  className?: string;
  children: ReactNode;
}) {
  return (
    <section className={className}>
      {title ? <h2>{title}</h2> : null}
      {children}
    </section>
  );
}
