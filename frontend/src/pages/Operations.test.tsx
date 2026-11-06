import {
  render,
  screen,
  fireEvent,
  waitFor,
  cleanup,
} from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import Dashboard from "./Dashboard";
import {
  Inventory,
  Agents,
  Allocation,
  Forecast,
  Simulation,
} from "./Operations";
const mocks = vi.hoisted(() => ({
  data: vi.fn(),
  post: vi.fn(),
  put: vi.fn(),
}));
vi.mock("../hooks/useData", () => ({ useData: mocks.data }));
vi.mock("../services/api", () => ({
  post: mocks.post,
  api: { put: mocks.put },
  errorText: (e: unknown) => String(e),
}));
vi.mock("recharts", () => ({
  AreaChart: () => null,
  Area: () => null,
  PieChart: () => null,
  Pie: () => null,
  Cell: () => null,
  ResponsiveContainer: () => null,
  LineChart: () => null,
  Line: () => null,
  XAxis: () => null,
  YAxis: () => null,
  Tooltip: () => null,
  CartesianGrid: () => null,
  BarChart: () => null,
  Bar: () => null,
}));
function mount(element: React.ReactNode) {
  return render(
    <QueryClientProvider
      client={
        new QueryClient({ defaultOptions: { queries: { retry: false } } })
      }
    >
      {element}
    </QueryClientProvider>,
  );
}
beforeEach(() => {
  mocks.post.mockResolvedValue({ id: 1 });
  mocks.data.mockReturnValue({ data: [] });
  mocks.put.mockResolvedValue({});
  vi.clearAllMocks();
});
afterEach(cleanup);
describe("API-connected workflows", () => {
  it("renders dashboard metrics returned by the API", () => {
    mocks.data.mockImplementation((path: string) => ({
      data:
        path === "/dashboard/summary"
          ? {
              total_inventory: 12345,
              total_products: 100,
              online_inventory: 400,
              offline_inventory: 800,
              low_stock: 7,
              stockout_risk: 0.02,
              total_warehouses: 6,
              total_stores: 15,
              estimated_savings: 0,
              pending_approvals: 0,
            }
          : [],
    }));
    mount(
      <MemoryRouter>
        <Dashboard />
      </MemoryRouter>,
    );
    expect(screen.getByText("12,345")).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Executive overview" }),
    ).toBeInTheDocument();
  });
  it("changes inventory query when search is entered", () => {
    mocks.data.mockReturnValue({ data: { items: [], total: 0 } });
    mount(<Inventory />);
    fireEvent.change(screen.getByLabelText("Search inventory"), {
      target: { value: "coffee" },
    });
    expect(mocks.data).toHaveBeenLastCalledWith(
      expect.stringContaining("search=coffee"),
    );
  });
  it("initiates the real agent endpoint", async () => {
    mount(<Agents />);
    fireEvent.click(screen.getByRole("button", { name: "Run all agents" }));
    await waitFor(() => expect(mocks.post).toHaveBeenCalledWith("/agents/run"));
  });
  it("requires review before invoking approval", async () => {
    mocks.data.mockImplementation((p: string) => ({
      data:
        p === "/optimization/runs"
          ? [
              {
                id: 1,
                run_name: "Test allocation",
                status: "waiting_for_approval",
                total_allocated: 10,
                total_cost: "12.50",
                objective_value: "12.50",
                details: {},
              },
            ]
          : [],
    }));
    mount(<Allocation />);
    fireEvent.click(screen.getByRole("button", { name: "Review approval" }));
    expect(mocks.post).not.toHaveBeenCalled();
    fireEvent.click(
      screen.getByRole("button", { name: "Approve and update inventory" }),
    );
    await waitFor(() =>
      expect(mocks.post).toHaveBeenCalledWith("/optimization/runs/1/approve"),
    );
  });
  it("posts forecast model and horizon", async () => {
    mocks.data.mockImplementation((p: string) => ({
      data: p.startsWith("/products")
        ? { items: [{ id: 1, product_name: "Coffee" }] }
        : [],
    }));
    mount(<Forecast />);
    fireEvent.change(screen.getByLabelText("Forecast horizon"), {
      target: { value: "14" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Generate forecast" }));
    await waitFor(() =>
      expect(mocks.post).toHaveBeenCalledWith("/forecast/run", {
        horizon: 14,
        model: "exponential_smoothing",
      }),
    );
  });
  it("runs a simulation without approving any inventory", async () => {
    mount(<Simulation />);
    fireEvent.click(screen.getByRole("button", { name: "Run scenario" }));
    await waitFor(() =>
      expect(mocks.post).toHaveBeenCalledWith("/simulation/run", {
        scenario: "online_surge",
        multiplier: 2,
      }),
    );
    expect(mocks.post).toHaveBeenCalledTimes(1);
  });
});
