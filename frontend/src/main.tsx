import React, { useState, useEffect } from "react";
import { createRoot } from "react-dom/client";
import {
  BrowserRouter,
  Routes,
  Route,
  NavLink,
  useLocation,
} from "react-router-dom";
import {
  QueryClient,
  QueryClientProvider,
  useQueryClient,
} from "@tanstack/react-query";
import {
  LayoutDashboard,
  Package,
  Network,
  TrendingUp,
  GitBranch,
  Warehouse,
  Truck,
  BarChart3,
  FlaskConical,
  Settings as SettingsIcon,
  Search,
  Bell,
  Menu,
  LogOut,
  ArrowUpRight,
  ChevronDown,
} from "lucide-react";
import Dashboard from "./pages/Dashboard";
import {
  Inventory,
  Agents,
  Allocation,
  Forecast,
  Warehouses,
  Logistics,
  Analytics,
  Simulation,
  Settings,
} from "./pages/Operations";
import { api, get, post, errorText } from "./services/api";
import { useData } from "./hooks/useData";
import { DataError } from "./components/DataError";
import "./styles.css";
const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1 } },
});
const navigation = [
  ["Overview", "/", LayoutDashboard],
  ["Inventory", "/inventory", Package],
  ["Agent control", "/agents", Network],
  ["Demand forecasting", "/forecast", TrendingUp],
  ["Allocation", "/allocation", GitBranch],
  ["Warehouses", "/warehouses", Warehouse],
  ["Logistics & transfers", "/logistics", Truck],
  ["Analytics & reports", "/analytics", BarChart3],
  ["Simulation center", "/simulation", FlaskConical],
] as const;
function Login({ onLogin }: { onLogin: () => void }) {
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  return (
    <div className="login-page">
      <div className="login-story">
        <div className="brand">
          <div className="brand-mark">
            <Network />
          </div>
          nexus<span>RETAIL INTELLIGENCE</span>
        </div>
        <div>
          <div className="eyebrow">
            CONNECTED INVENTORY. COORDINATED INTELLIGENCE.
          </div>
          <h1>
            The right stock.
            <br />
            The right place.
            <br />
            <em>Every channel.</em>
          </h1>
          <p>
            One intelligent workspace for your stores, warehouses and online
            fulfillment network.
          </p>
          <div className="login-network">
            <Warehouse size={44} />
            <span />
            <Network size={70} />
            <span />
            <Package size={44} />
          </div>
        </div>
        <small>Autonomous recommendations. Human-approved decisions.</small>
      </div>
      <form
        className="login-form"
        onSubmit={async (e) => {
          e.preventDefault();
          setBusy(true);
          setError("");
          try {
            const r = await post("/auth/login", { username, password });
            sessionStorage.setItem("token", r.access_token);
            onLogin();
          } catch (err) {
            setError(errorText(err));
          } finally {
            setBusy(false);
          }
        }}
      >
        <div className="eyebrow">WELCOME TO NEXUS</div>
        <h2>Your network starts here.</h2>
        <p>Sign in to your retail intelligence workspace.</p>
        <label className="field">
          Username
          <input
            autoComplete="username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            required
          />
        </label>
        <label className="field">
          Password
          <input
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
        </label>
        {error && (
          <p role="alert" className="error">
            {error}
          </p>
        )}
        <button className="primary" disabled={busy}>
          {busy ? "Signing in…" : "Sign in to workspace"}
          <ArrowUpRight size={18} />
        </button>
        <div className="demo-hint">
          Local demo: <b>admin</b> / <b>RetailDemo!2026</b>
          <br />
          Read-only access: <b>analyst</b> / same password
        </div>
      </form>
    </div>
  );
}
function Shell({ logout }: { logout: () => void }) {
  const location = useLocation();
  const client = useQueryClient();
  const [collapsed, setCollapsed] = useState(false);
  const [alerts, setAlerts] = useState(false);
  const [live, setLive] = useState(false);
  const { data: user } = useData("/auth/me");
  const { data: notifications = [] } = useData("/notifications");
  const { data: preferences } = useData("/preferences");
  const active =
    navigation.find((n) => n[1] === location.pathname)?.[0] ?? "Settings";
  useEffect(() => {
    window.scrollTo(0, 0);
  }, [location.pathname]);
  useEffect(() => {
    const ws = new WebSocket(
      `${window.location.protocol === "https:" ? "wss" : "ws"}://${window.location.host}/ws/events`,
    );
    ws.onopen = () =>
      ws.send(JSON.stringify({ token: sessionStorage.getItem("token") }));
    ws.onmessage = () => {
      setLive(true);
      client.invalidateQueries();
    };
    ws.onclose = () => setLive(false);
    const timer = setInterval(() => {
      get("/events")
        .then(() => client.invalidateQueries())
        .catch(() => {});
    }, 30000);
    return () => {
      ws.close();
      clearInterval(timer);
    };
  }, [client]);
  return (
    <div className={`app ${collapsed ? "collapsed" : ""}`}>
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">
            <Network size={23} />
          </div>
          <div>
            nexus<small>RETAIL INTELLIGENCE</small>
          </div>
        </div>
        <div className="workspace-label">
          WORKSPACE <ChevronDown size={13} />
        </div>
        <div className="workspace">
          <span>R</span>
          <div>
            Retail operations<small>Omnichannel workspace</small>
          </div>
        </div>
        <div className="nav-label">MANAGE YOUR NETWORK</div>
        <nav>
          {navigation.map(([name, path, Icon]) => (
            <NavLink
              key={path}
              aria-label={name}
              title={name}
              to={path}
              end={path === "/"}
            >
              <Icon size={18} />
              <span>{name}</span>
              {path === "/agents" && <small>10</small>}
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="engine-status">
            <span className="live-dot" />
            <div>
              Intelligence engine<small>Local models · no API key</small>
            </div>
          </div>
          <NavLink aria-label="Settings" title="Settings" to="/settings">
            <SettingsIcon size={18} />
            <span>Settings</span>
          </NavLink>
          <button aria-label="Sign out" title="Sign out" onClick={logout}>
            <LogOut size={17} />
            <span>Sign out</span>
          </button>
          <div className="sidebar-version">
            NEXUS PLATFORM <span>v1.0</span>
          </div>
        </div>
      </aside>
      <main>
        <header>
          <div className="breadcrumb">
            <button
              className="icon-button"
              aria-label="Toggle sidebar"
              onClick={() => setCollapsed(!collapsed)}
            >
              <Menu size={19} />
            </button>
            <span>Workspace</span>
            <span>/</span>
            <b>{active}</b>
          </div>
          <div className="top-actions">
            <span className="connection">
              <span className="live-dot" />
              {live ? "Live updates" : "Connected · 30s refresh"}
            </span>
            <button
              className="icon-button notification-button"
              aria-label="Notifications"
              onClick={() => setAlerts(!alerts)}
            >
              <Bell size={19} />
              {preferences?.notifications_enabled !== false &&
                notifications.some((n: any) => !n.read) && <i />}
            </button>
            <span className="avatar">
              {user?.username?.slice(0, 1).toUpperCase() ?? "A"}
            </span>
            <div className="user-info">
              <b>{user?.username ?? "Workspace"}</b>
              <small>{user?.role ?? "Authenticated"}</small>
            </div>
          </div>
          {alerts && (
            <div className="notification-panel">
              <h3>Notifications</h3>
              {notifications.map((n: any) => (
                <button
                  key={n.id}
                  onClick={async () => {
                    await api.put(`/notifications/${n.id}/read`);
                    client.invalidateQueries();
                  }}
                >
                  <span className={n.read ? "" : "unread"}>{n.message}</span>
                  <small>{new Date(n.created_at).toLocaleString()}</small>
                </button>
              ))}
            </div>
          )}
        </header>
        <div className="page-content">
          <DataError />
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/inventory" element={<Inventory />} />
            <Route path="/agents" element={<Agents />} />
            <Route path="/forecast" element={<Forecast />} />
            <Route path="/allocation" element={<Allocation />} />
            <Route path="/warehouses" element={<Warehouses />} />
            <Route path="/logistics" element={<Logistics />} />
            <Route path="/analytics" element={<Analytics />} />
            <Route path="/simulation" element={<Simulation />} />
            <Route path="/settings" element={<Settings />} />
            <Route path="*" element={<Dashboard />} />
          </Routes>
          <footer>
            <span>© 2026 Nexus Retail Intelligence</span>
            <span>Connected channels. Coordinated decisions.</span>
          </footer>
        </div>
      </main>
    </div>
  );
}
export function App() {
  const [auth, setAuth] = useState(!!sessionStorage.getItem("token"));
  const logout = () => {
    sessionStorage.removeItem("token");
    queryClient.clear();
    setAuth(false);
  };
  useEffect(() => {
    window.addEventListener("session-expired", logout);
    return () => window.removeEventListener("session-expired", logout);
  }, []);
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        {auth ? (
          <Shell logout={logout} />
        ) : (
          <Login onLogin={() => setAuth(true)} />
        )}
      </BrowserRouter>
    </QueryClientProvider>
  );
}
createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
