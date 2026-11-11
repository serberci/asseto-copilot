import type { HTMLInputTypeAttribute } from "react";

export function TextInput({
  value,
  onChange,
  disabled,
}: {
  value: string;
  onChange: (value: string) => void;
  disabled?: boolean;
}) {
  return <input value={value} onChange={(event) => onChange(event.target.value)} disabled={disabled} />;
}

export function TextField({
  label,
  value,
  onChange,
  type = "text",
  autoComplete,
  maxLength,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  type?: HTMLInputTypeAttribute;
  autoComplete?: string;
  maxLength?: number;
}) {
  return (
    <label>
      {label}
      <input
        value={value}
        onChange={(event) => onChange(event.target.value)}
        type={type}
        autoComplete={autoComplete}
        maxLength={maxLength}
      />
    </label>
  );
}
