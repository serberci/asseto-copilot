import { useEffect, useState } from "react";
import { getMe, logout, type Identity } from "@/api";
import { Account } from "@/account/Account";
import { LapsPage } from "@/laps/LapsPage";
import { PerformancePage } from "@/performance/PerformancePage";
import { CurrentSession } from "@/session/CurrentSession";
import { BrandHeader, Note, Page, Tabs } from "@/ui";
import { Login } from "./Login";

const TABS = [
  { id: "account", label: "Account" },
  { id: "session", label: "Current Session" },
  { id: "laps", label: "Laps" },
  { id: "performance", label: "Performance" },
] as const;

type Tab = (typeof TABS)[number]["id"];

export function App() {
  const [identity, setIdentity] = useState<Identity | null>(null);
  const [ready, setReady] = useState(false);
  const [tab, setTab] = useState<Tab>("session");

  useEffect(() => {
    getMe()
      .then(setIdentity)
      .catch(() => setIdentity(null))
      .finally(() => setReady(true));
  }, []);

  if (!ready) {
    return (
      <Page>
        <Note>Loading</Note>
      </Page>
    );
  }
  if (!identity) return <Login onSuccess={setIdentity} />;

  return (
    <Page>
      <BrandHeader>
        <button
          type="button"
          onClick={() => {
            void logout().finally(() => {
              setTab("session");
              setIdentity(null);
            });
          }}
        >
          Log out
        </button>
      </BrandHeader>
      <Note>{identity.role === "administrator" ? "Administrator" : identity.display_name}</Note>
      <Tabs tabs={TABS} value={tab} onChange={setTab} />
      {tab === "account" ? <Account identity={identity} /> : null}
      {tab === "session" ? <CurrentSession /> : null}
      {tab === "laps" ? <LapsPage /> : null}
      {tab === "performance" ? <PerformancePage /> : null}
    </Page>
  );
}
