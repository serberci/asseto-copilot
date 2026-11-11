import { useState } from "react";
import { claimUnassigned, createDriver, deleteDriver, revokeDriver, type DriverAccount } from "@/api";
import { Form, Note, TextField, errorMessage } from "@/ui";

export function DriverAdmin({
  drivers,
  onChanged,
  onError,
}: {
  drivers: DriverAccount[];
  onChanged: () => Promise<void>;
  onError: (message: string | null) => void;
}) {
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");

  async function addDriver() {
    try {
      await createDriver(name.trim(), password);
      setName("");
      setPassword("");
      await onChanged();
      onError(null);
    } catch (reason) {
      onError(errorMessage(reason, "The driver was not created."));
    }
  }

  async function claim(driverId: string) {
    try {
      await claimUnassigned(driverId);
      await onChanged();
    } catch (reason) {
      onError(errorMessage(reason, "The laps were not assigned."));
    }
  }

  async function revoke(driverId: string) {
    try {
      await revokeDriver(driverId);
      await onChanged();
    } catch (reason) {
      onError(errorMessage(reason, "The login was not revoked."));
    }
  }

  async function remove(driver: DriverAccount) {
    if (!window.confirm(`Delete ${driver.display_name}? Their laps stay and become unassigned.`)) return;
    try {
      await deleteDriver(driver.id);
      await onChanged();
    } catch (reason) {
      onError(errorMessage(reason, "The driver was not deleted."));
    }
  }

  return (
    <>
      <h2>Drivers</h2>
      <Form kind="login" onSubmit={addDriver}>
        <TextField label="Name" value={name} onChange={setName} maxLength={40} />
        <TextField label="Password" value={password} onChange={setPassword} type="password" />
        <button type="submit">Create driver</button>
      </Form>
      <Note>Tell the driver this password. It is not shown again.</Note>
      <ul className="drivers">
        {drivers.map((driver) => (
          <li key={driver.id}>
            <span>{driver.revoked ? "revoked" : "active"}</span>
            <p>
              {driver.display_name}
              {driver.revoked ? null : (
                <>
                  {" "}
                  <button type="button" onClick={() => void claim(driver.id)}>
                    Assign unassigned laps
                  </button>{" "}
                  <button type="button" onClick={() => void revoke(driver.id)}>
                    Revoke login
                  </button>
                </>
              )}{" "}
              <button type="button" onClick={() => void remove(driver)}>
                Delete
              </button>
            </p>
          </li>
        ))}
      </ul>
    </>
  );
}
