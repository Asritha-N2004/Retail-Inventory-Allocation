import { Link } from "react-router-dom";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
  PieChart,
  Pie,
  Cell,
  BarChart,
  Bar,
} from "recharts";
import {
  Package,
  Warehouse,
  Store,
  ShieldAlert,
  ArrowRight,
  Network,
  Activity,
} from "lucide-react";
import { useData } from "../hooks/useData";
import { Card, Metric, Badge, number, money } from "../components/ui";
const colors = ["#4263eb", "#10b8a6", "#f3b554", "#ef6e76"];
export default function Dashboard() {
  const { data: s } = useData("/dashboard/summary");
  const { data: sales = [] } = useData("/dashboard/sales-performance");
  const { data: channels = [] } = useData("/dashboard/channel-performance");
  const { data: health = [] } = useData("/dashboard/inventory-health");
  const { data: agents = [] } = useData("/agents");
  const { data: locations = [] } = useData("/locations");
  const trends = Object.values(
    sales.reduce((a: any, r: any) => {
      a[r.month] ??= { month: r.month.slice(5), online: 0, offline: 0 };
      a[r.month][r.channel] = r.units;
      return a;
    }, {}),
  );
  return (
    <>
      <div className="page-intro">
        <div>
          <div className="eyebrow">YOUR NETWORK, IN SYNC</div>
          <h1>Executive overview</h1>
          <p>A clear view of your inventory. A smarter move for every unit.</p>
        </div>
        <Link className="primary" to="/allocation">
          <Network size={17} /> Intelligent allocation <ArrowRight size={16} />
        </Link>
      </div>
      <div className="hero-strip">
        <span className="live-dot" />
        <b>One connected retail network</b>
        <span>
          {s?.total_warehouses ?? "—"} supply locations <i />{" "}
          {s?.total_stores ?? "—"} retail stores <i /> 1 online fulfillment
          center
        </span>
        <Link to="/agents">
          Explore your agents <ArrowRight size={14} />
        </Link>
      </div>
      <div className="metrics">
        <Metric
          label="Total inventory"
          value={number(s?.total_inventory)}
          detail={`${number(s?.total_products)} active products across all locations`}
          icon={<Package size={18} />}
        />
        <Metric
          label="Online availability"
          value={number(s?.online_inventory)}
          detail="E-commerce fulfillment inventory"
          icon={<Warehouse size={18} />}
        />
        <Metric
          label="Store inventory"
          value={number(s?.offline_inventory)}
          detail="Across 15 physical retail stores"
          icon={<Store size={18} />}
        />
        <Metric
          label="Positions needing attention"
          value={number(s?.low_stock)}
          detail={`${number((s?.stockout_risk ?? 0) * 100)}% below safety stock`}
          icon={<ShieldAlert size={18} />}
        />
      </div>
      <div className="grid-2 wide-left">
        <Card
          title="Demand across channels"
          subtitle="Historical units sold · 12 months"
          action={
            <span className="chart-key">
              <i /> Online <i /> In-store
            </span>
          }
        >
          <div className="chart">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={trends}>
                <defs>
                  <linearGradient id="blue" x1="0" y1="0" x2="0" y2="1">
                    <stop stopColor="#4263eb" stopOpacity={0.18} />
                    <stop offset="1" stopColor="#4263eb" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid vertical={false} stroke="#edf0f6" />
                <XAxis dataKey="month" axisLine={false} tickLine={false} />
                <YAxis
                  axisLine={false}
                  tickLine={false}
                  tickFormatter={(v) => `${v / 1000}k`}
                />
                <Tooltip />
                <Area
                  type="monotone"
                  dataKey="offline"
                  stroke="#10b8a6"
                  strokeWidth={2.5}
                  fill="#10b8a6"
                  fillOpacity={0.06}
                />
                <Area
                  type="monotone"
                  dataKey="online"
                  stroke="#4263eb"
                  strokeWidth={2.5}
                  fill="url(#blue)"
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </Card>
        <Card
          title="Inventory distribution"
          subtitle="Current units by channel"
        >
          <div className="donut">
            <ResponsiveContainer width="100%" height={190}>
              <PieChart>
                <Pie
                  data={channels}
                  dataKey="units"
                  innerRadius={62}
                  outerRadius={83}
                  paddingAngle={5}
                  stroke="none"
                >
                  {channels.map((_: any, i: number) => (
                    <Cell key={i} fill={colors[i]} />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
            <div className="donut-center">
              <strong>3</strong>
              <small>connected channels</small>
            </div>
          </div>
          <div className="legend">
            {channels.map((r: any, i: number) => (
              <div key={r.name}>
                <span>
                  <i style={{ background: colors[i] }} />
                  {r.name}
                </span>
                <b>{number(r.units)}</b>
              </div>
            ))}
          </div>
        </Card>
      </div>
      <div className="grid-3">
        <Card title="Inventory health" subtitle="Live stock positions">
          <div className="health-list">
            {health.map((r: any, i: number) => (
              <div key={r.name}>
                <div>
                  <Badge>{r.name}</Badge>
                  <b>{number(r.value)}</b>
                </div>
                <div className="progress">
                  <span
                    style={{ width: `${r.value / 22}%`, background: colors[i] }}
                  />
                </div>
              </div>
            ))}
          </div>
        </Card>
        <Card
          title="Network capacity"
          subtitle="Supply locations · stock on hand"
        >
          <div className="chart small">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={locations.filter(
                  (l: any) =>
                    l.location_type === "Warehouse" ||
                    l.location_type === "Distribution Center",
                )}
                layout="vertical"
              >
                <XAxis type="number" hide />
                <YAxis
                  type="category"
                  dataKey="region"
                  axisLine={false}
                  tickLine={false}
                  width={80}
                />
                <Tooltip />
                <Bar
                  dataKey="units"
                  fill="#4263eb"
                  radius={[0, 4, 4, 0]}
                  barSize={13}
                />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>
        <Card
          title="Agent activity"
          subtitle="Auditable decisions, shared intelligence"
          action={<Activity size={18} color="#10b8a6" />}
        >
          <div className="activity-list">
            {agents.slice(0, 4).map((a: any) => (
              <div key={a.id}>
                <div className="activity-icon">
                  <Network size={16} />
                </div>
                <div>
                  <b>{a.name}</b>
                  <small>
                    {a.latest
                      ? new Date(a.latest.created_at).toLocaleString()
                      : "Ready for first execution"}
                  </small>
                </div>
                <span className={`status-dot ${a.status}`} />
              </div>
            ))}
          </div>
          <Link className="text-link" to="/agents">
            Open control center <ArrowRight size={14} />
          </Link>
        </Card>
      </div>
      <div className="insight-strip">
        <div>
          <span className="eyebrow">ALLOCATION INTELLIGENCE</span>
          <h3>Turn visibility into your next best move.</h3>
          <p>
            {s?.pending_approvals ?? 0} allocation runs await review. Forecast,
            optimize, then approve with confidence.
          </p>
        </div>
        <div>
          <strong>{money(s?.estimated_savings ?? 0)}</strong>
          <small>Modeled avoided costs · approved runs</small>
        </div>
        <Link to="/allocation" className="secondary">
          Review allocations <ArrowRight size={15} />
        </Link>
      </div>
    </>
  );
}
