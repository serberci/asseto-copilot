import { useEffect, useState } from "react";
import { getBenchmark, getLive, setReference, type Lap, type LiveView } from "@/api";
import { errorMessage } from "@/ui/error-message";

export function useLiveDashboard() {
  const [live, setLive] = useState<LiveView | null>(null);
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [analysisLoss, setAnalysisLoss] = useState<number | null>(null);

  useEffect(() => {
    let closed = false;
    let socket: WebSocket | null = null;
    getLive()
      .then((view) => {
        if (!closed) setLive(view);
      })
      .catch((reason: unknown) => {
        if (!closed) setError(errorMessage(reason, "The live session could not be loaded."));
      });
    const protocol = window.location.protocol === "https:" ? "wss" : "ws";
    socket = new WebSocket(`${protocol}://${window.location.host}/ws/dashboard`);
    socket.onopen = () => setConnected(true);
    socket.onclose = () => setConnected(false);
    socket.onmessage = (event) => {
      const payload = JSON.parse(event.data) as { type: string } & LiveView;
      if (payload.type === "snapshot") setLive(payload);
    };
    return () => {
      closed = true;
      socket?.close();
    };
  }, []);

  const latestValidId = live?.laps.filter((lap) => lap.valid).at(-1)?.id;
  useEffect(() => {
    if (!latestValidId) {
      setAnalysisLoss(null);
      return;
    }
    getBenchmark(latestValidId)
      .then((report) => setAnalysisLoss(report.personal.time_loss_s))
      .catch(() => setAnalysisLoss(null));
  }, [latestValidId]);

  async function chooseReference(lap: Lap) {
    if (!live?.session) return;
    try {
      await setReference(live.session.id, lap.id);
      setLive(await getLive());
      setError(null);
    } catch (reason) {
      setError(errorMessage(reason, "The reference lap was not saved."));
    }
  }

  return { live, connected, error, setError, analysisLoss, chooseReference };
}
