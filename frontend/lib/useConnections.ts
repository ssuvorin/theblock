"use client";

import { useCallback, useEffect, useState } from "react";
import { apiMessage, fetchApi } from "@/lib/api";
import { useApiData } from "@/lib/useApi";
import type {
  Connection,
  ConnectionStatusResponse,
  ConnectionsResponse,
  SourceCatalogEntry,
  SourceCatalogResponse,
} from "@/lib/types";

type ConnectResponse = { redirect_url?: string; qr_code_base64?: string };

interface CallbackOutcome {
  status: "ok" | "error";
  source: string;
  reason?: string;
}

const load = async () => {
  const [catalog, connections] = await Promise.all([
    fetchApi<SourceCatalogResponse>("/api/connections/sources"),
    fetchApi<ConnectionsResponse>("/api/connections"),
  ]);
  return { catalog, connections };
};

/**
 * State for the connections screen: the catalog, the owner's connections, and the actions.
 *
 * The OAuth outcome is read from the URL the backend redirected to and then stripped from the
 * address bar, so a refresh does not resurrect a banner about an authorization that finished
 * minutes ago.
 */
export function useConnections() {
  const { data, loaded, error, setError, reload } = useApiData(load);
  const [busy, setBusy] = useState("");
  const [history, setHistory] = useState<ConnectionStatusResponse | null>(null);
  const outcome = useCallbackOutcome();

  const act = useCallback(
    async (key: string, run: () => Promise<unknown>) => {
      setBusy(key);
      setError("");
      try {
        await run();
        await reload();
      } catch (requestError) {
        setError(apiMessage(requestError));
      } finally {
        setBusy("");
      }
    },
    [reload, setError],
  );

  const connect = useCallback(
    (source: SourceCatalogEntry) =>
      act(source.source, async () => {
        const response = await fetchApi<ConnectResponse>(
          `/api/connections/${source.source}/connect`,
          { method: "POST" },
        );
        if (response.redirect_url) window.location.assign(response.redirect_url);
      }),
    [act],
  );

  const sync = useCallback(
    (connection: Connection) =>
      act(connection.id, () =>
        fetchApi(`/api/connections/${connection.id}/sync`, { method: "POST" }),
      ),
    [act],
  );

  const togglePause = useCallback(
    (connection: Connection) =>
      act(connection.id, () =>
        fetchApi(`/api/connections/${connection.id}/${connection.paused ? "resume" : "pause"}`, {
          method: "POST",
        }),
      ),
    [act],
  );

  const disconnect = useCallback(
    (connection: Connection, deleteData: boolean) =>
      act(connection.id, () =>
        fetchApi(`/api/connections/${connection.id}?delete_data=${deleteData}`, {
          method: "DELETE",
        }),
      ),
    [act],
  );

  const inspect = useCallback(
    (connection: Connection) =>
      act(connection.id, async () => {
        setHistory(
          await fetchApi<ConnectionStatusResponse>(`/api/connections/${connection.id}/status`),
        );
      }),
    [act],
  );

  return {
    catalog: data?.catalog.sources ?? [],
    connections: data?.connections.connections ?? [],
    loaded,
    error,
    busy,
    history,
    outcome,
    reload,
    connect,
    sync,
    togglePause,
    disconnect,
    inspect,
    clearHistory: () => setHistory(null),
  };
}

function useCallbackOutcome(): CallbackOutcome | null {
  const [outcome, setOutcome] = useState<CallbackOutcome | null>(null);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const status = params.get("status");
    if (status !== "ok" && status !== "error") return;
    setOutcome({
      status,
      source: params.get("source") ?? "the source",
      reason: params.get("reason") ?? undefined,
    });
    window.history.replaceState({}, "", window.location.pathname);
  }, []);

  return outcome;
}
