import { useEffect, type ReactNode } from "react";

export function Drawer({
  label,
  eyebrow,
  title,
  onClose,
  children,
}: {
  label: string;
  eyebrow: string;
  title: ReactNode;
  onClose: () => void;
  children: ReactNode;
}) {
  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    window.addEventListener("keydown", onKey);
    return () => {
      document.body.style.overflow = previous;
      window.removeEventListener("keydown", onKey);
    };
  }, [onClose]);

  return (
    <div className="drawer-backdrop" onClick={onClose}>
      <aside className="drawer" role="dialog" aria-modal="true" aria-label={label} onClick={(event) => event.stopPropagation()}>
        <header>
          <div>
            <p className="eyebrow">{eyebrow}</p>
            <h2>{title}</h2>
          </div>
          <button type="button" onClick={onClose}>
            Close
          </button>
        </header>
        {children}
      </aside>
    </div>
  );
}
