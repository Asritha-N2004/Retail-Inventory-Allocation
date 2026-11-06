import { Preferences, UserRoles } from "../components/Preferences";
import { useState, useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";
import {
  Search,
  Play,
  Check,
  X,
  ArrowRight,
  RotateCcw,
  Network,
  ChevronRight,
} from "lucide-react";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  BarChart,
  Bar,
} from "recharts";
import { useData } from "../hooks/useData";
import { api, post, errorText } from "../services/api";
import {
  Card,
  Metric,
  Table,
  Badge,
  number,
  money,
  ExportButton,
} from "../components/ui";
import type { RecordData } from "../types";

export function useAction() {
  const client = useQueryClient();
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  return {
    busy,
    message,
    run: async (fn: () => Promise<unknown>) => {
      setBusy(true);
      setMessage("");
      try {
        const result = await fn();
        setMessage("Operation completed successfully.");
        await client.invalidateQueries();
        return result;
      } catch (e) {
        setMessage(errorText(e));
      } finally {
        setBusy(false);
      }
    },
  };
}
export function Intro({
  title,
  description,
  children,
}: {
  title: string;
  description: string;
  children?: React.ReactNode;
}) {
  return (
    <div className="page-intro">
      <div>
        <div className="eyebrow">RETAIL OPERATIONS</div>
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      {children}
    </div>
  );
}
export function Message({ text }: { text: string }) {
  return text ? (
    <div role="status" className="message">
      {text}
    </div>
  ) : null;
}

export function Inventory() {
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [channel, setChannel] = useState("");
  const [page, setPage] = useState(1);
  const [sort, setSort] = useState("sku");
  const [selected, setSelected] = useState<RecordData | null>(null);
  const a = useAction();
  const { data } = useData(
    `/inventory?search=${encodeURIComponent(search)}&status=${status}&channel=${channel}&page=${page}&sort=${sort}`,
  );
  return (
    <>
      <Intro
        title="Inventory management"
        description="Every product. Every location. One accurate view."
      >
        <ExportButton />
      </Intro>
      <div className="toolbar">
        <label className="search">
          <Search size={17} />
          <input
            aria-label="Search inventory"
            placeholder="Search product or SKU…"
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(1);
            }}
          />
        </label>
        <select
          aria-label="Stock status"
          value={status}
          onChange={(e) => {
            setStatus(e.target.value);
            setPage(1);
          }}
        >
          <option value="">All stock statuses</option>
          {["healthy", "low", "critical", "excess"].map((s) => (
            <option key={s}>{s}</option>
          ))}
        </select>
        <select
          aria-label="Channel"
          value={channel}
          onChange={(e) => {
            setChannel(e.target.value);
            setPage(1);
          }}
        >
          <option value="">All channels</option>
          <option>online</option>
          <option>offline</option>
          <option>warehouse</option>
        </select>
        <select
          aria-label="Sort inventory"
          value={sort}
          onChange={(e) => setSort(e.target.value)}
        >
          <option value="sku">Sort by SKU</option>
          <option value="quantity_available">Sort by availability</option>
          <option value="location_name">Sort by location</option>
        </select>
      </div>
      <Card
        title="Network inventory"
        subtitle={`${number(data?.total)} stock positions · select a row to inspect or adjust`}
      >
        <Table
          rows={data?.items ?? []}
          onClick={(r) => setSelected({ ...r })}
          columns={[
            { key: "sku", label: "SKU", render: (r) => <code>{r.sku}</code> },
            { key: "product_name", label: "Product" },
            { key: "location_name", label: "Location" },
            { key: "channel", label: "Channel" },
            { key: "quantity_on_hand", label: "On hand" },
            { key: "quantity_reserved", label: "Reserved" },
            { key: "quantity_available", label: "Available" },
            { key: "safety_stock", label: "Safety" },
            {
              key: "status",
              label: "Status",
              render: (r) => <Badge>{r.status}</Badge>,
            },
          ]}
        />
        <div className="pagination">
          <span>
            Page {page} of {Math.max(1, Math.ceil((data?.total ?? 0) / 25))}
          </span>
          <button
            className="secondary"
            disabled={page === 1}
            onClick={() => setPage(page - 1)}
          >
            Previous
          </button>
          <button
            className="secondary"
            disabled={page * 25 >= (data?.total ?? 0)}
            onClick={() => setPage(page + 1)}
          >
            Next
          </button>
        </div>
      </Card>
      <Message text={a.message} />
      {selected && (
        <div className="overlay">
          <form
            className="drawer"
            onSubmit={(e) => {
              e.preventDefault();
              a.run(async () => {
                await api.put(`/inventory/${selected.id}`, {
                  quantity_on_hand: Number(selected.quantity_on_hand),
                  quantity_reserved: Number(selected.quantity_reserved),
                  safety_stock: Number(selected.safety_stock),
                  reorder_level: Number(selected.reorder_level),
                  version: selected.version,
                });
                setSelected(null);
              });
            }}
          >
            <button
              type="button"
              className="icon-button close"
              aria-label="Close details"
              onClick={() => setSelected(null)}
            >
              <X />
            </button>
            <div className="eyebrow">PRODUCT DETAILS</div>
            <h2>{selected.product_name}</h2>
            <code>{selected.sku}</code>
            <p>
              {selected.category} · {selected.location_name}
            </p>
            <Badge>{selected.status}</Badge>
            {[
              "quantity_on_hand",
              "quantity_reserved",
              "safety_stock",
              "reorder_level",
            ].map((k) => (
              <label className="field" key={k}>
                {k.replaceAll("_", " ")}
                <input
                  type="number"
                  min="0"
                  required
                  value={selected[k]}
                  onChange={(e) =>
                    setSelected({ ...selected, [k]: e.target.value })
                  }
                />
              </label>
            ))}
            <p className="muted">
              Changes are version-checked and recorded in the audit ledger.
            </p>
            <button disabled={a.busy} className="primary">
              Save inventory adjustment
            </button>
          </form>
        </div>
      )}
    </>
  );
}

export function Agents() {
  const { data: agents = [] } = useData("/agents");
  const { data: logs = [] } = useData("/agents/logs");
  const { data: messages = [] } = useData("/agents/messages");
  const a = useAction();
  return (
    <>
      <Intro
        title="Multi-agent control center"
        description="Ten specialist agents. One coordinated inventory strategy."
      >
        <button
          className="primary"
          disabled={a.busy}
          onClick={() => a.run(() => post("/agents/run"))}
        >
          <Play size={16} />
          {a.busy ? "Executing workflow…" : "Run all agents"}
        </button>
      </Intro>
      <Message text={a.message} />
      <div className="workflow">
        {[
          "Forecast",
          "Monitor",
          "Channel needs",
          "Supply & risk",
          "Allocate",
          "Logistics",
          "Review",
        ].map((s, i) => (
          <span key={s}>
            <b>{i + 1}</b>
            {s}
            {i < 6 && <ChevronRight size={16} />}
          </span>
        ))}
      </div>
      <div className="agent-grid">
        {agents.map((agent: any, i: number) => (
          <Card
            key={agent.id}
            title={agent.name}
            subtitle={agent.role}
            action={
              <span className="agent-icon">
                <Network size={20} />
              </span>
            }
          >
            <div className="agent-status">
              <Badge>{agent.status}</Badge>
              <small>AGENT {String(i + 1).padStart(2, "0")}</small>
            </div>
            <div className="agent-output">
              {agent.latest
                ? JSON.stringify(agent.latest.output_summary).slice(0, 200)
                : "Ready to receive structured recommendations."}
            </div>
            <div className="agent-footer">
              <span>{agent.tasks_completed} tasks completed</span>
              <button
                title="Runs agent with its dependency workflow"
                className="text-button"
                disabled={a.busy}
                onClick={() =>
                  a.run(() => post("/agents/run", { agent_id: agent.id }))
                }
              >
                Run with dependencies <Play size={12} />
              </button>
            </div>
          </Card>
        ))}
      </div>
      <div className="grid-2">
        <Card
          title="Execution history"
          subtitle="Real persisted backend executions"
        >
          <Table
            rows={logs.slice(0, 20)}
            columns={[
              { key: "agent_name", label: "Agent" },
              { key: "execution_id", label: "Run" },
              {
                key: "status",
                label: "Status",
                render: (r) => <Badge>{r.status}</Badge>,
              },
              {
                key: "execution_duration",
                label: "Duration",
                render: (r) => `${(r.execution_duration ?? 0).toFixed(2)}s`,
              },
            ]}
          />
        </Card>
        <Card
          title="Agent communication"
          subtitle="Structured messages exchanged through shared state"
        >
          <div className="communication">
            {messages.slice(0, 12).map((m: any) => (
              <div key={m.id}>
                <b>
                  {m.sender} <ArrowRight size={12} /> {m.receiver}
                </b>
                <code>{JSON.stringify(m.payload).slice(0, 220)}</code>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </>
  );
}

export function Allocation() {
  const { data: runs = [] } = useData("/optimization/runs");
  const [chosen, setChosen] = useState<number | null>(null);
  const id = chosen ?? runs[0]?.id;
  const { data: recs = [] } = useData(
    id ? `/optimization/runs/${id}/recommendations` : "/optimization/runs",
  );
  const run = runs.find((r: any) => r.id === id);
  const a = useAction();
  const [confirm, setConfirm] = useState(false);
  return (
    <>
      <Intro
        title="Intelligent inventory allocation"
        description="Demand-led decisions. Constraint-valid transfers. Your final approval."
      >
        <button
          className="primary"
          disabled={a.busy}
          onClick={() =>
            a.run(async () => {
              const r = await post("/optimization/run");
              setChosen(r.id);
            })
          }
        >
          <Network size={17} />
          {a.busy ? "Optimizing network…" : "Run Intelligent Allocation"}
        </button>
      </Intro>
      <Message text={a.message} />
      <div className="notice">
        <ShieldIcon /> Recommendations do not change inventory. Approval
        atomically updates the allocation ledger and creates planned shipments.
      </div>
      <div className="toolbar">
        <label>
          Allocation run{" "}
          <select
            aria-label="Allocation run"
            value={id ?? ""}
            onChange={(e) => {
              setChosen(Number(e.target.value));
              setConfirm(false);
            }}
          >
            {runs.map((r: any) => (
              <option key={r.id} value={r.id}>
                #{r.id} · {r.run_name} · {r.status}
              </option>
            ))}
          </select>
        </label>
        {run && <Badge>{run.status}</Badge>}
      </div>
      {run ? (
        <>
          <div className="metrics">
            <Metric
              label="Recommended units"
              value={number(run.total_allocated)}
            />
            <Metric
              label="Transfer & operating cost"
              value={money(run.total_cost)}
            />
            <Metric
              label="Shortage units avoided"
              value={number(
                (run.details?.baseline_shortage ?? 0) -
                  (run.details?.remaining_shortage ?? 0),
              )}
            />
            <Metric
              label="Modeled cost savings"
              value={money(run.details?.estimated_savings ?? 0)}
              detail={`Solver: ${run.details?.method ?? "manual"}`}
            />
          </div>
          <Card
            title="Allocation recommendations"
            subtitle={`Run #${id} · objective ${money(run.objective_value)} · remaining shortage ${number(run.details?.remaining_shortage)}`}
            action={
              <ExportButton
                path={`/reports/allocations/${id}.csv`}
                filename={`allocation-${id}.csv`}
              />
            }
          >
            <Table
              rows={recs}
              columns={[
                { key: "sku", label: "Product" },
                { key: "source", label: "Source" },
                { key: "destination", label: "Destination" },
                { key: "sales_channel", label: "Channel" },
                { key: "allocated_quantity", label: "Units" },
                { key: "destination_before", label: "Before" },
                { key: "destination_after", label: "Projected" },
                {
                  key: "estimated_cost",
                  label: "Cost",
                  render: (r) => money(r.estimated_cost),
                },
                {
                  key: "allocation_status",
                  label: "Status",
                  render: (r) => <Badge>{r.allocation_status}</Badge>,
                },
                { key: "explanation", label: "Reason" },
              ]}
            />
          </Card>
          <div className="approval-bar">
            <div>
              <b>Human oversight, built in.</b>
              <p>
                Approval rechecks stock, reservations and capacity against
                current inventory.
              </p>
            </div>
            {run.status === "waiting_for_approval" && (
              <>
                <button
                  className="secondary"
                  disabled={a.busy}
                  onClick={() =>
                    a.run(() => post(`/optimization/runs/${id}/reject`))
                  }
                >
                  <X size={16} /> Reject
                </button>
                <button
                  className="primary"
                  disabled={a.busy}
                  onClick={() => setConfirm(true)}
                >
                  <Check size={16} /> Review approval
                </button>
              </>
            )}
            {run.status === "approved" && (
              <button
                className="secondary"
                disabled={a.busy}
                onClick={() =>
                  a.run(() => post(`/optimization/runs/${id}/rollback`))
                }
              >
                <RotateCcw size={16} /> Compensate allocation
              </button>
            )}
          </div>
          {confirm && (
            <div className="overlay">
              <div className="modal">
                <div className="eyebrow">CONFIRM INVENTORY CHANGE</div>
                <h2>Approve run #{id}?</h2>
                <p>
                  This will move {number(run.total_allocated)} units between
                  inventory locations and create planned transfers. Every
                  adjustment is audited.
                </p>
                <div className="button-row">
                  <button
                    className="secondary"
                    onClick={() => setConfirm(false)}
                  >
                    Cancel
                  </button>
                  <button
                    className="primary"
                    disabled={a.busy}
                    onClick={() =>
                      a.run(async () => {
                        await post(`/optimization/runs/${id}/approve`);
                        setConfirm(false);
                      })
                    }
                  >
                    Approve and update inventory
                  </button>
                </div>
                <Message text={a.message} />
              </div>
            </div>
          )}
        </>
      ) : (
        <div className="empty big">
          <Network size={42} />
          <h2>Your next best allocation starts here.</h2>
          <p>
            Run the coordinated agent workflow to generate a reviewable
            proposal.
          </p>
        </div>
      )}
    </>
  );
}
function ShieldIcon() {
  return <Check size={17} />;
}

export function Forecast() {
  const { data: products } = useData("/products?page_size=100");
  const { data: locations = [] } = useData("/locations");
  const [pid, setPid] = useState(1);
  const [lid, setLid] = useState(7);
  const [horizon, setHorizon] = useState(7);
  const [model, setModel] = useState("exponential_smoothing");
  const { data: history = [] } = useData(
    `/sales/history?product_id=${pid}&location_id=${lid}`,
  );
  const { data: forecasts = [] } = useData(
    `/forecast?product_id=${pid}&location_id=${lid}`,
  );
  const a = useAction();
  const [comparison, setComparison] = useState<any[]>([]);
  const { data: preferences } = useData("/preferences");
  useEffect(() => {
    if (preferences?.model && Number.isInteger(preferences.horizon)) {
      setHorizon(preferences.horizon);
      setModel(preferences.model);
    }
  }, [preferences?.model, preferences?.horizon]);
  const f = forecasts[0];
  return (
    <>
      <Intro
        title="Demand forecasting"
        description="Local statistical models. Transparent uncertainty. Channel-specific demand."
      />
      <div className="toolbar">
        <select
          aria-label="Forecast product"
          value={pid}
          onChange={(e) => setPid(Number(e.target.value))}
        >
          {products?.items.map((p: any) => (
            <option key={p.id} value={p.id}>
              {p.product_name}
            </option>
          ))}
        </select>
        <select
          aria-label="Forecast location"
          value={lid}
          onChange={(e) => setLid(Number(e.target.value))}
        >
          {locations
            .filter((l: any) =>
              ["Physical Store", "Online Fulfillment Center"].includes(
                l.location_type,
              ),
            )
            .map((l: any) => (
              <option key={l.id} value={l.id}>
                {l.location_name}
              </option>
            ))}
        </select>
        <select
          aria-label="Forecast model"
          value={model}
          onChange={(e) => setModel(e.target.value)}
        >
          {[
            "moving_average",
            "exponential_smoothing",
            "linear_regression",
            "random_forest",
          ].map((m) => (
            <option key={m} value={m}>
              {m.replaceAll("_", " ")}
            </option>
          ))}
        </select>
        <label>
          Days{" "}
          <input
            aria-label="Forecast horizon"
            type="number"
            min={1}
            max={90}
            value={horizon}
            onChange={(e) => setHorizon(Number(e.target.value))}
          />
        </label>
        <button
          className="primary"
          disabled={a.busy}
          onClick={() => a.run(() => post("/forecast/run", { horizon, model }))}
        >
          <Play size={15} />
          {a.busy ? "Forecasting…" : "Generate forecast"}
        </button>
        <button
          className="secondary"
          disabled={a.busy}
          onClick={() =>
            a.run(async () =>
              setComparison(
                await post("/forecast/compare", {
                  product_id: pid,
                  location_id: lid,
                  horizon,
                }),
              ),
            )
          }
        >
          Compare models
        </button>
      </div>
      <Message text={a.message} />
      <div className="metrics">
        <Metric
          label="Predicted demand"
          value={f ? number(f.predicted_demand) : "—"}
          detail={
            f
              ? `${f.metrics.horizon}-day forecast · ${f.channel}`
              : "Generate a forecast to begin"
          }
        />
        <Metric
          label="95% approximate interval"
          value={f ? `${number(f.lower_bound)}–${number(f.upper_bound)}` : "—"}
        />
        <Metric
          label="Holdout accuracy"
          value={f ? `${(f.confidence_score * 100).toFixed(1)}%` : "—"}
          detail="1 − capped holdout WAPE"
        />
        <Metric
          label="Mean absolute error"
          value={f?.metrics.mae ?? "—"}
          detail="Units per day · holdout window"
        />
      </div>
      <Card
        title="Historical demand & forecast"
        subtitle="Daily unit sales · forecast shown as horizon daily average"
      >
        <div className="chart tall">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart
              data={[
                ...history.map((h: any) => ({
                  date: h.sale_date.slice(5),
                  actual: h.quantity_sold,
                })),
                ...(f
                  ? Array.from({ length: f.metrics.horizon }, (_, i) => ({
                      date: `+${i + 1}d`,
                      forecast: f.predicted_demand / f.metrics.horizon,
                      lower: f.lower_bound / f.metrics.horizon,
                      upper: f.upper_bound / f.metrics.horizon,
                    }))
                  : []),
              ]}
            >
              <CartesianGrid vertical={false} stroke="#edf0f6" />
              <XAxis dataKey="date" minTickGap={35} />
              <YAxis />
              <Tooltip />
              <Line
                dataKey="actual"
                stroke="#4263eb"
                dot={false}
                strokeWidth={2}
              />
              <Line
                dataKey="forecast"
                stroke="#10b8a6"
                dot={false}
                strokeWidth={2}
              />
              <Line
                dataKey="lower"
                stroke="#9edbd4"
                dot={false}
                strokeDasharray="4 4"
              />
              <Line
                dataKey="upper"
                stroke="#9edbd4"
                dot={false}
                strokeDasharray="4 4"
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </Card>
      {comparison.length > 0 && (
        <Card
          title="Model comparison"
          subtitle="Same history and forecast horizon across four local models"
        >
          <Table
            rows={comparison}
            columns={[
              { key: "model_name", label: "Model" },
              { key: "predicted_demand", label: "Demand" },
              { key: "lower_bound", label: "Lower bound" },
              { key: "upper_bound", label: "Upper bound" },
              {
                key: "metrics",
                label: "Holdout WAPE",
                render: (r) => `${(r.metrics.wape * 100).toFixed(1)}%`,
              },
            ]}
          />
        </Card>
      )}
    </>
  );
}

export function Warehouses() {
  const { data: locations = [] } = useData("/locations");
  const { data: transfers = [] } = useData("/transfers");
  return (
    <>
      <Intro
        title="Warehouse network"
        description="Available supply and capacity across your distribution network."
      />
      <div className="agent-grid">
        {locations
          .filter((l: any) =>
            [
              "Warehouse",
              "Distribution Center",
              "Online Fulfillment Center",
            ].includes(l.location_type),
          )
          .map((l: any) => (
            <Card key={l.id} title={l.location_name} subtitle={l.region}>
              <Badge>{l.location_type}</Badge>
              <div className="warehouse-units">
                {number(l.units)} <small>units on hand</small>
              </div>
              <div className="progress">
                <span
                  style={{
                    width: `${Math.min(100, (l.units / l.storage_capacity) * 100)}%`,
                  }}
                />
              </div>
              <div className="capacity-meta">
                <span>
                  {((l.units / l.storage_capacity) * 100).toFixed(1)}% utilized
                </span>
                <span>{number(l.storage_capacity)} capacity</span>
              </div>
              <p className="muted">
                {
                  transfers.filter(
                    (t: any) =>
                      t.destination_location_id === l.id &&
                      t.status !== "delivered",
                  ).length
                }{" "}
                incoming ·{" "}
                {
                  transfers.filter(
                    (t: any) =>
                      t.source_location_id === l.id && t.status !== "delivered",
                  ).length
                }{" "}
                outgoing shipments
              </p>
            </Card>
          ))}
      </div>
    </>
  );
}

export function Logistics() {
  const { data: transfers = [] } = useData("/transfers");
  const { data: locations = [] } = useData("/locations");
  const a = useAction();
  const location = (id: number) =>
    locations.find((l: any) => l.id === id)?.location_name ?? id;
  return (
    <>
      <Intro
        title="Logistics & transfers"
        description="Track approved inventory movements from plan to delivery."
      />
      <Message text={a.message} />
      <div className="metrics">
        {["planned", "in_transit", "delivered", "cancelled"].map((status) => (
          <Metric
            key={status}
            label={status.replaceAll("_", " ")}
            value={transfers.filter((t: any) => t.status === status).length}
            detail="Recorded shipment status"
          />
        ))}
      </div>
      <Card
        title="Transfer tracking"
        subtitle="Approval changes the allocation ledger; shipment states track physical movement separately."
      >
        <Table
          rows={transfers}
          columns={[
            { key: "id", label: "Transfer" },
            { key: "product_id", label: "Product ID" },
            {
              key: "source_location_id",
              label: "Source",
              render: (r) => location(r.source_location_id),
            },
            {
              key: "destination_location_id",
              label: "Destination",
              render: (r) => location(r.destination_location_id),
            },
            { key: "quantity", label: "Units" },
            {
              key: "estimated_cost",
              label: "Cost",
              render: (r) => money(r.estimated_cost),
            },
            {
              key: "estimated_hours",
              label: "ETA",
              render: (r) => `${r.estimated_hours}h`,
            },
            {
              key: "status",
              label: "Status",
              render: (r) => <Badge>{r.status}</Badge>,
            },
            {
              key: "action",
              label: "Next step",
              render: (r) =>
                ["planned", "in_transit"].includes(r.status) ? (
                  <button
                    disabled={a.busy}
                    className="text-button"
                    onClick={() =>
                      a.run(() =>
                        api.put(`/transfers/${r.id}/status`, {
                          status:
                            r.status === "planned" ? "in_transit" : "delivered",
                        }),
                      )
                    }
                  >
                    {r.status === "planned" ? "Dispatch" : "Mark delivered"}{" "}
                    <ArrowRight size={12} />
                  </button>
                ) : (
                  "—"
                ),
            },
          ]}
        />
      </Card>
    </>
  );
}

export function Analytics() {
  const { data: s } = useData("/dashboard/summary");
  const { data: accuracy } = useData("/analytics/forecast-accuracy");
  const { data: runs = [] } = useData("/optimization/runs");
  const { data: audit = [] } = useData("/audit");
  return (
    <>
      <Intro
        title="Analytics & reports"
        description="Trace every decision. Measure the operational impact."
      >
        <div className="button-row">
          <ExportButton />
          <button className="secondary" onClick={() => window.print()}>
            Print / Save PDF
          </button>
        </div>
      </Intro>
      <div className="metrics">
        <Metric
          label="Inventory turnover"
          value={`${s?.inventory_turnover ?? "—"}×`}
          detail="Annual sales units / current stock proxy"
        />
        <Metric
          label="Forecast WAPE"
          value={
            accuracy?.count ? `${(accuracy.mean_wape * 100).toFixed(1)}%` : "—"
          }
          detail="Seven-day holdout aggregate error"
        />
        <Metric
          label="Approved savings estimate"
          value={money(s?.estimated_savings ?? 0)}
          detail="Modeled avoided cost, not realized profit"
        />
        <Metric label="Overstock positions" value={number(s?.overstock)} />
      </div>
      <Card title="Allocation performance" subtitle="Persisted run outcomes">
        <div className="chart">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={[...runs].reverse()}>
              <CartesianGrid vertical={false} stroke="#edf0f6" />
              <XAxis dataKey="id" />
              <YAxis />
              <Tooltip />
              <Bar
                dataKey="total_allocated"
                fill="#4263eb"
                radius={[4, 4, 0, 0]}
              />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </Card>
      <Card
        title="Inventory audit ledger"
        subtitle="Previous and new values for every inventory-changing operation"
      >
        <Table
          rows={audit}
          columns={[
            {
              key: "timestamp",
              label: "Timestamp",
              render: (r) => new Date(r.timestamp).toLocaleString(),
            },
            { key: "user_id", label: "User" },
            {
              key: "action",
              label: "Action",
              render: (r) => <Badge>{r.action}</Badge>,
            },
            { key: "entity_type", label: "Entity" },
            { key: "entity_id", label: "Record" },
            {
              key: "previous_value",
              label: "Before",
              render: (r) => <code>{JSON.stringify(r.previous_value)}</code>,
            },
            {
              key: "new_value",
              label: "After",
              render: (r) => <code>{JSON.stringify(r.new_value)}</code>,
            },
          ]}
        />
      </Card>
    </>
  );
}

export function Simulation() {
  const [scenario, setScenario] = useState("online_surge");
  const [multiplier, setMultiplier] = useState(2);
  const { data: runs = [] } = useData("/simulation/runs");
  const [selected, setSelected] = useState<any>(null);
  const a = useAction();
  const sim = selected ?? runs[0];
  const r = sim?.results;
  return (
    <>
      <Intro
        title="Simulation center"
        description="Stress-test your network. Explore the outcome before moving a single unit."
      />
      <div className="simulation-banner">
        <div>
          <div className="eyebrow">A SAFE SPACE FOR WHAT IF</div>
          <h2>Prepare for the unexpected.</h2>
          <p>
            Simulate demand shocks and supply disruptions against your current
            network.
          </p>
        </div>
        <Network size={90} strokeWidth={0.8} />
      </div>
      <div className="toolbar">
        <select
          aria-label="Simulation scenario"
          value={scenario}
          onChange={(e) => setScenario(e.target.value)}
        >
          {[
            "online_surge",
            "store_surge",
            "warehouse_shortage",
            "supplier_delay",
            "seasonal_surge",
            "regional_imbalance",
            "promotion_spike",
          ].map((s) => (
            <option key={s} value={s}>
              {s.replaceAll("_", " ")}
            </option>
          ))}
        </select>
        <label>
          Channel surge multiplier{" "}
          <input
            type="number"
            min="1"
            max="5"
            step=".1"
            value={multiplier}
            onChange={(e) => setMultiplier(Number(e.target.value))}
          />
        </label>
        <button
          className="primary"
          disabled={a.busy}
          onClick={() =>
            a.run(async () =>
              setSelected(
                await post("/simulation/run", { scenario, multiplier }),
              ),
            )
          }
        >
          <Play size={15} />
          {a.busy ? "Simulating…" : "Run scenario"}
        </button>
      </div>
      <Message text={a.message} />
      {r && (
        <>
          <div className="metrics">
            <Metric
              label="Initial inventory"
              value={number(r.initial_inventory)}
              detail="Read-only snapshot"
            />
            <Metric
              label="Simulated demand"
              value={number(r.simulated_demand)}
            />
            <Metric
              label="Units reallocated"
              value={number(r.total_allocated)}
            />
            <Metric
              label="Modeled avoided cost"
              value={money(r.estimated_savings)}
            />
          </div>
          <div className="grid-2">
            <Card
              title="Baseline vs optimized"
              subtitle={`${sim.scenario.replaceAll("_", " ")} · inventory unchanged`}
            >
              <div className="chart">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart
                    data={[
                      {
                        name: "No reallocation",
                        shortage: r.baseline_shortage,
                      },
                      { name: "Optimized", shortage: r.remaining_shortage },
                    ]}
                  >
                    <XAxis dataKey="name" />
                    <YAxis />
                    <Tooltip />
                    <Bar
                      dataKey="shortage"
                      fill="#4263eb"
                      radius={[5, 5, 0, 0]}
                    />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </Card>
            <Card
              title="Scenario results"
              subtitle="Same optimizer, isolated proposed movements"
            >
              <div className="result-list">
                <div>
                  <span>Optimization method</span>
                  <b>{r.method}</b>
                </div>
                <div>
                  <span>Operational cost</span>
                  <b>{money(r.total_cost)}</b>
                </div>
                <div>
                  <span>Remaining shortage</span>
                  <b>{number(r.remaining_shortage)}</b>
                </div>
                <div>
                  <span>Inventory changed</span>
                  <Badge>no</Badge>
                </div>
              </div>
            </Card>
          </div>
        </>
      )}
      <Card
        title="Scenario history"
        subtitle="Reproducible inputs and saved outcomes"
      >
        <Table
          rows={runs}
          onClick={setSelected}
          columns={[
            { key: "id", label: "Run" },
            { key: "scenario", label: "Scenario" },
            {
              key: "created_at",
              label: "Created",
              render: (r) => new Date(r.created_at).toLocaleString(),
            },
            {
              key: "results",
              label: "Shortage avoided",
              render: (r) =>
                number(
                  r.results.baseline_shortage - r.results.remaining_shortage,
                ),
            },
          ]}
        />
      </Card>
    </>
  );
}

export function Settings() {
  const { data: s } = useData("/settings");
  const [weights, setWeights] = useState<RecordData | null>(null);
  const a = useAction();
  const w = weights ?? s?.optimization;
  return (
    <>
      <Intro
        title="Settings & system"
        description="Tune your allocation policy and inspect system health."
      />
      <Message text={a.message} />
      <div className="grid-2">
        <Card
          title="Optimization policy"
          subtitle="Applied to future proposals. Existing recommendations retain their original estimates."
        >
          <form
            onSubmit={(e) => {
              e.preventDefault();
              a.run(() => api.put("/settings", w));
            }}
          >
            {w &&
              Object.entries(w).map(([k, v]) => (
                <label className="field" key={k}>
                  {k.replaceAll("_", " ")}
                  <input
                    type="number"
                    min={
                      k === "online_priority" || k === "stockout_penalty"
                        ? ".01"
                        : "0"
                    }
                    step=".01"
                    required
                    value={String(v)}
                    onChange={(e) =>
                      setWeights({ ...w, [k]: Number(e.target.value) })
                    }
                  />
                </label>
              ))}
            <button className="primary" disabled={a.busy}>
              Save configuration
            </button>
          </form>
        </Card>
        <div>
          <Card title="Your profile" subtitle="Authenticated session">
            <div className="profile-avatar">
              {s?.user.username.slice(0, 1).toUpperCase()}
            </div>
            <h2>{s?.user.username}</h2>
            <Badge>{s?.user.role}</Badge>
            <p className="muted">
              Inventory-changing actions require Administrator or Inventory
              Manager permission.
            </p>
          </Card>
          <Card title="System health" subtitle="Live service checks">
            <div className="result-list">
              <div>
                <span>API service</span>
                <Badge>{s?.health.status ?? "checking"}</Badge>
              </div>
              <div>
                <span>Database</span>
                <Badge>{s?.health.database ?? "checking"}</Badge>
              </div>
              <div>
                <span>Forecasting</span>
                <b>4 local models</b>
              </div>
              <div>
                <span>Execution mode</span>
                <b>Deterministic · no LLM required</b>
              </div>
            </div>
          </Card>
          <Preferences />
          {s?.user.role === "Administrator" && <UserRoles />}
          <Card title="Roles" subtitle="Permission groups">
            {s?.roles.map((r: string) => (
              <p key={r}>{r}</p>
            ))}
          </Card>
        </div>
      </div>
    </>
  );
}
