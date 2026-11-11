import { useCallback, useEffect, useState } from "react";
import {
  issueAgentToken,
  listDrivers,
  listLaps,
  type CatalogLap,
  type DriverAccount,
  type Identity,
} from "@/api";
import { Answer, ErrorText, Form, Note, Section, errorMessage } from "@/ui";
import { DriverAdmin } from "./DriverAdmin";
import { LapAssignment } from "./LapAssignment";

export function Account({ identity }: { identity: Identity }) {
  const [token, setToken] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const isAdmin = identity.role === "administrator";
  const catalog = useAdminCatalog(isAdmin, setError);

  async function generate() {
    try {
      setToken((await issueAgentToken()).token);
      setError(null);
    } catch (reason) {
      setError(errorMessage(reason, "The token was not created."));
    }
  }

  return (
    <Section title="Account">
      {identity.role === "driver" ? (
        <Form kind="ask" onSubmit={generate}>
          <button type="submit">Generate agent token</button>
        </Form>
      ) : (
        <Note>Drivers generate their own agent token after they log in.</Note>
      )}
      {token ? (
        <Answer note={token}>
          Copy this token into the Windows agent. It is shown once. If it is lost, generate another one and paste that
          into the agent.
        </Answer>
      ) : null}
      {isAdmin ? (
        <>
          <DriverAdmin drivers={catalog.drivers} onChanged={catalog.reload} onError={setError} />
          <LapAssignment laps={catalog.laps} drivers={catalog.drivers} onChanged={catalog.reload} onError={setError} />
        </>
      ) : null}
      <ErrorText>{error}</ErrorText>
    </Section>
  );
}

function useAdminCatalog(enabled: boolean, onError: (message: string) => void) {
  const [drivers, setDrivers] = useState<DriverAccount[]>([]);
  const [laps, setLaps] = useState<CatalogLap[]>([]);

  const reload = useCallback(async () => {
    const [listed, catalog] = await Promise.all([listDrivers(), listLaps()]);
    setDrivers(listed.drivers);
    setLaps(catalog.laps);
  }, []);

  useEffect(() => {
    if (!enabled) return;
    void reload().catch((reason: unknown) => onError(errorMessage(reason, "The account could not be loaded.")));
  }, [enabled, reload, onError]);

  return { drivers, laps, reload };
}
