import { useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { errorText } from "../services/api";
export function DataError() {
  const [message, setMessage] = useState("");
  const client = useQueryClient();
  const [, refresh] = useState(0);
  const [dismissed, setDismissed] = useState("");
  useEffect(
    () => client.getQueryCache().subscribe(() => refresh((value) => value + 1)),
    [client],
  );
  useEffect(() => {
    const handler = (e: Event) => setMessage((e as CustomEvent).detail);
    window.addEventListener("api-error", handler);
    return () => window.removeEventListener("api-error", handler);
  }, []);
  const failure = client
    .getQueryCache()
    .findAll()
    .find(
      (query) =>
        query.getObserversCount() > 0 && query.state.status === "error",
    );
  const failureId = failure
    ? `${failure.queryHash}:${failure.state.errorUpdatedAt}`
    : "";
  const requestError =
    failure && failureId !== dismissed
      ? `${String(failure.queryKey[0]).split("?")[0]}: ${errorText(failure.state.error)}`
      : "";
  const visibleMessage = message || requestError;
  return visibleMessage ? (
    <div role="alert" className="message error">
      Unable to load current data: {visibleMessage}
      <div className="button-row">
        <button
          className="text-button"
          onClick={() => {
            setMessage("");
            setDismissed(failureId);
            client.invalidateQueries();
          }}
        >
          Retry requests
        </button>
        <button
          className="text-button"
          onClick={() => {
            setMessage("");
            setDismissed(failureId);
          }}
        >
          Dismiss
        </button>
      </div>
    </div>
  ) : null;
}
