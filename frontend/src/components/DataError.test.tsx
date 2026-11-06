import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import {
  QueryClient,
  QueryClientProvider,
  useQuery,
} from "@tanstack/react-query";
import { DataError } from "./DataError";

afterEach(cleanup);
describe("Current API failures", () => {
  it("identifies the failed endpoint and clears after a successful retry", async () => {
    const request = vi
      .fn()
      .mockRejectedValueOnce(new Error("Server unavailable"))
      .mockResolvedValue({ items: [] });
    const client = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    function DashboardRequest() {
      useQuery({
        queryKey: ["/dashboard/sales-performance"],
        queryFn: request,
      });
      return <DataError />;
    }
    render(
      <QueryClientProvider client={client}>
        <DashboardRequest />
      </QueryClientProvider>,
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "/dashboard/sales-performance",
    );
    await client.refetchQueries();
    await waitFor(() =>
      expect(screen.queryByRole("alert")).not.toBeInTheDocument(),
    );
    expect(request).toHaveBeenCalledTimes(2);
  });
  it("does not show cached errors from pages with no active request observers", () => {
    const client = new QueryClient();
    const query = client
      .getQueryCache()
      .build(client, { queryKey: ["/old-page"] });
    query.setState({
      status: "error",
      error: new Error("Old failure"),
      errorUpdatedAt: Date.now(),
    });
    render(
      <QueryClientProvider client={client}>
        <DataError />
      </QueryClientProvider>,
    );
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });
});
