import type { ReactNode } from "react";

export function Table({ headers, children }: { headers: readonly string[]; children: ReactNode }) {
  return (
    <table>
      <thead>
        <tr>
          {headers.map((header, index) => (
            <th key={`${header}-${index}`}>{header}</th>
          ))}
        </tr>
      </thead>
      <tbody>{children}</tbody>
    </table>
  );
}
