import type { FormEvent, ReactNode } from "react";

export function Form({
  kind,
  onSubmit,
  children,
}: {
  kind: "login" | "ask";
  onSubmit: (event: FormEvent) => void | Promise<void>;
  children: ReactNode;
}) {
  return (
    <form
      className={kind}
      onSubmit={(event) => {
        event.preventDefault();
        void onSubmit(event);
      }}
    >
      {children}
    </form>
  );
}
