import type { ReactNode } from "react";

export function SelectField({
  label,
  value,
  onChange,
  children,
}: {
  label?: string;
  value: string;
  onChange: (value: string) => void;
  children: ReactNode;
}) {
  const control = (
    <select value={value} onChange={(event) => onChange(event.target.value)}>
      {children}
    </select>
  );
  if (!label) return control;
  return (
    <label>
      {label}
      {control}
    </label>
  );
}

export function TrackSelect({
  tracks,
  value,
  onChange,
  allLabel,
}: {
  tracks: readonly string[];
  value: string;
  onChange: (track: string) => void;
  allLabel?: string;
}) {
  return (
    <SelectField label="Track" value={value} onChange={onChange}>
      {allLabel ? <option value="">{allLabel}</option> : null}
      {tracks.map((track) => (
        <option key={track} value={track}>
          {track}
        </option>
      ))}
    </SelectField>
  );
}
