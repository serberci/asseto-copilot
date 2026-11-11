import { useState } from "react";
import { assignLap, type CatalogLap, type DriverAccount } from "@/api";
import { lapTime } from "@/format";
import { Note, SelectField, Table, errorMessage } from "@/ui";

export function LapAssignment({
  laps,
  drivers,
  onChanged,
  onError,
}: {
  laps: CatalogLap[];
  drivers: DriverAccount[];
  onChanged: () => Promise<void>;
  onError: (message: string) => void;
}) {
  const [choice, setChoice] = useState<Record<string, string>>({});
  const activeDrivers = drivers.filter((driver) => !driver.revoked);

  async function assign(lap: CatalogLap) {
    const selected = choice[lap.id] ?? lap.driver_id ?? "";
    try {
      await assignLap(lap.id, selected || null);
      await onChanged();
      setChoice((current) => {
        const next = { ...current };
        delete next[lap.id];
        return next;
      });
    } catch (reason) {
      onError(errorMessage(reason, "The lap was not assigned."));
    }
  }

  return (
    <>
      <h2>Laps</h2>
      <Note>Choose a driver for one lap. Unassigned leaves the lap with nobody.</Note>
      {laps.length === 0 ? <Note>No laps yet.</Note> : null}
      <Table headers={["Track", "Car", "Lap", "Time", "Driver", ""]}>
        {laps.map((lap) => (
          <tr key={lap.id}>
            <td>{lap.track_id}</td>
            <td>{lap.car_model}</td>
            <td>{lap.lap_number}</td>
            <td>{lapTime(lap.lap_time_ms)}</td>
            <td>
              <SelectField
                value={choice[lap.id] ?? lap.driver_id ?? ""}
                onChange={(driverId) => setChoice({ ...choice, [lap.id]: driverId })}
              >
                <option value="">Unassigned</option>
                {activeDrivers.map((driver) => (
                  <option key={driver.id} value={driver.id}>
                    {driver.display_name}
                  </option>
                ))}
              </SelectField>
            </td>
            <td>
              <button type="button" onClick={() => void assign(lap)}>
                Assign
              </button>
            </td>
          </tr>
        ))}
      </Table>
    </>
  );
}
