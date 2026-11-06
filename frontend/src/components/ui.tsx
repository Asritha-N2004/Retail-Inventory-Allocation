import { useState, type ReactNode } from "react";
import { Download, ArrowUpRight } from "lucide-react";
import { api } from "../services/api";
export function Badge({ children }: { children: ReactNode }) {
  return (
    <span className={`badge ${String(children).replaceAll(" ", "_")}`}>
      {String(children).replaceAll("_", " ")}
    </span>
  );
}
export function Card({
  title,
  subtitle,
  children,
  action,
}: {
  title: string;
  subtitle?: string;
  children: ReactNode;
  action?: ReactNode;
}) {
  return (
    <section className="card">
      <div className="card-heading">
        <div>
          <h3>{title}</h3>
          {subtitle && <p>{subtitle}</p>}
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}
export function Metric({
  label,
  value,
  detail,
  icon,
}: {
  label: string;
  value: ReactNode;
  detail?: string;
  icon?: ReactNode;
}) {
  return (
    <div className="metric">
      <div className="metric-top">
        {label}
        <span>{icon || <ArrowUpRight size={17} />}</span>
      </div>
      <strong>{value}</strong>
      <small>{detail || "From current network inventory"}</small>
    </div>
  );
}
export function Table({
  columns,
  rows,
  onClick,
}: {
  columns: { key: string; label: string; render?: (row: any) => ReactNode }[];
  rows: any[];
  onClick?: (row: any) => void;
}) {
  const [requestedPage, setPage] = useState(1);
  const pages = Math.max(1, Math.ceil(rows.length / 25));
  const page = Math.min(requestedPage, pages);
  const visible = rows.slice((page - 1) * 25, page * 25);
  return (
    <>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              {columns.map((c) => (
                <th key={c.key}>{c.label}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {visible.map((r, i) => (
              <tr
                key={r.id ?? i}
                tabIndex={onClick ? 0 : undefined}
                onKeyDown={(e) => {
                  if (e.key === "Enter") onClick?.(r);
                }}
                onClick={() => onClick?.(r)}
                className={onClick ? "clickable" : ""}
              >
                {columns.map((c) => (
                  <td
                    title={typeof r[c.key] === "string" ? r[c.key] : undefined}
                    key={c.key}
                  >
                    {c.render ? c.render(r) : String(r[c.key] ?? "—")}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
        {!rows.length && (
          <div className="empty">
            No records yet. Run a workflow or adjust your filters.
          </div>
        )}
      </div>
      {pages > 1 && (
        <div className="pagination">
          <span>
            {rows.length} records · page {page} of {pages}
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
            disabled={page === pages}
            onClick={() => setPage(page + 1)}
          >
            Next
          </button>
        </div>
      )}
    </>
  );
}
export const number = (n: number | null | undefined) =>
  n == null
    ? "—"
    : new Intl.NumberFormat("en-IN", { maximumFractionDigits: 0 }).format(n);
export const money = (n: number | string) =>
  new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  }).format(Number(n));
export function ExportButton({
  path = "/reports/inventory.csv",
  filename = "nexus-inventory.csv",
}: {
  path?: string;
  filename?: string;
}) {
  return (
    <button
      className="secondary"
      onClick={async () => {
        try {
          const r = await api.get(path, { responseType: "blob" });
          const url = URL.createObjectURL(r.data);
          const a = document.createElement("a");
          a.href = url;
          a.download = filename;
          a.click();
          URL.revokeObjectURL(url);
        } catch {
          window.dispatchEvent(
            new CustomEvent("api-error", {
              detail:
                "Report could not be downloaded. Retry after checking the connection.",
            }),
          );
        }
      }}
    >
      <Download size={15} /> Export CSV
    </button>
  );
}
