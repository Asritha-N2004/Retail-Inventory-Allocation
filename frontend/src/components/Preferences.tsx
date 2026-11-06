import { useState } from "react";
import { useData } from "../hooks/useData";
import { api, errorText } from "../services/api";
import { useQueryClient } from "@tanstack/react-query";
import { Card, Table } from "./ui";
export function Preferences() {
  const { data: p } = useData("/preferences");
  const { data: s } = useData("/settings");
  const [draft, setDraft] = useState<any>(null);
  const [message, setMessage] = useState("");
  const client = useQueryClient();
  const w = draft ?? p;
  return (
    <Card title="Workspace preferences" subtitle="Saved for your account">
      <form
        onSubmit={async (e) => {
          e.preventDefault();
          try {
            await api.put("/preferences", w);
            client.invalidateQueries();
            setMessage("Preferences saved.");
          } catch (err) {
            setMessage(errorText(err));
          }
        }}
      >
        {w && (
          <>
            <label className="field">
              Preferred forecast model
              <select
                value={w.model}
                onChange={(e) => setDraft({ ...w, model: e.target.value })}
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
            </label>
            <label className="field">
              Preferred horizon (days)
              <input
                type="number"
                min="1"
                max="90"
                required
                value={w.horizon}
                onChange={(e) =>
                  setDraft({ ...w, horizon: Number(e.target.value) })
                }
              />
            </label>
            <label className="checkbox-field">
              <input
                type="checkbox"
                checked={w.notifications_enabled}
                onChange={(e) =>
                  setDraft({ ...w, notifications_enabled: e.target.checked })
                }
              />{" "}
              Highlight unread notifications
            </label>
          </>
        )}
        <button className="primary">Save preferences</button>
        {message && (
          <p role="status" className="muted">
            {message}
          </p>
        )}
      </form>
    </Card>
  );
}
export function UserRoles() {
  const { data: users = [] } = useData("/users");
  const { data: s } = useData("/settings");
  const [message, setMessage] = useState("");
  const client = useQueryClient();
  return (
    <Card
      title="Role management"
      subtitle="Administrators control inventory approval permissions"
    >
      <Table
        rows={users}
        columns={[
          { key: "username", label: "Username" },
          {
            key: "role",
            label: "Permission group",
            render: (u) => (
              <select
                aria-label={`Role for ${u.username}`}
                value={u.role}
                onChange={async (e) => {
                  try {
                    await api.put(`/users/${u.id}/role`, {
                      role: e.target.value,
                    });
                    await client.invalidateQueries();
                    setMessage("Role updated and audited.");
                  } catch (err) {
                    setMessage(errorText(err));
                  }
                }}
              >
                {s?.roles.map((r: string) => (
                  <option key={r}>{r}</option>
                ))}
              </select>
            ),
          },
        ]}
      />
      {message && (
        <p role="status" className="muted">
          {message}
        </p>
      )}
    </Card>
  );
}
