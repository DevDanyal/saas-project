"use client";

import { useCallback, useEffect, useState } from "react";
import { formatDate } from "@/lib/format";
import { get, patch } from "@/lib/api";
import type { ActionItem } from "@/lib/types";
import { useUser } from "@/lib/user-context";
import { CheckCircle2, Clock, Filter } from "lucide-react";

type FilterState = "open" | "done" | "cancelled" | "all";

export default function ActionsPage() {
  const { activeId } = useUser();
  const [items, setItems] = useState<ActionItem[] | null>(null);
  const [filter, setFilter] = useState<FilterState>("open");
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!activeId) return;
    const r = await get<{ action_items: ActionItem[] }>(`/emails/action-items/${activeId}?status=all`);
    setItems(r.action_items);
  }, [activeId]);

  useEffect(() => { if (activeId) load().catch((e) => setError(e instanceof Error ? e.message : String(e))); }, [activeId, load]);

  async function setStatus(id: string, status: "done" | "cancelled" | "open") {
    setBusyId(id); setError(null);
    try { await patch(`/emails/action-items/${id}`, { status }); await load(); }
    catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setBusyId(null); }
  }

  if (!activeId) return <div className="empty"><h2>No account</h2><p>Connect to view extracted action items.</p></div>;
  if (items === null) return <div className="card card-pad sub">Loading action items…</div>;

  const open = items.filter((i) => i.status === "open").length;
  const done = items.filter((i) => i.status === "done").length;
  const visible = [...items].filter((i) => filter === "all" || i.status === filter).sort((a, b) => (a.due ?? "9999").localeCompare(b.due ?? "9999"));

  return (
    <div className="stack">
      <div className="page-head">
        <div>
          <h1>Action Items</h1>
          <div className="sub">{open} open · {done} completed — extracted automatically from your inbox.</div>
        </div>
        <div className="row" style={{ flexWrap: "wrap" }}>
          {(["open", "done", "cancelled", "all"] as FilterState[]).map((f) => (
            <button key={f} className={`btn sm ${filter === f ? "primary" : ""}`} onClick={() => setFilter(f)}>{f}</button>
          ))}
        </div>
      </div>

      {error && <div className="error-banner">{error}</div>}

      <div className="grid-3">
        <div className="kpi"><div className="kpi-label">Open</div><div className="kpi-value">{open}</div><div className="kpi-meta">Needs attention</div></div>
        <div className="kpi"><div className="kpi-label">Completed</div><div className="kpi-value">{done}</div><div className="kpi-meta">Marked done</div></div>
        <div className="kpi"><div className="kpi-label">Total</div><div className="kpi-value">{items.length}</div><div className="kpi-meta">All extracted tasks</div></div>
      </div>

      {visible.length === 0 ? (
        <div className="empty"><h2>No action items</h2><p>{filter === "open" ? "You’re all caught up. New tasks will appear here when extracted from emails." : "No items match this filter."}</p></div>
      ) : (
        <div className="card" style={{ padding: 4 }}>
          {visible.map((i) => (
            <div key={i.id} className="action-item" style={{ padding: "12px 14px" }}>
              <span className={`chip ${i.status === "done" ? "ok" : i.type === "call" ? "hot" : "warn"}`}>{i.type}</span>
              <div className="desc">
                <div style={{ fontWeight: 600, fontSize: 13.5, textDecoration: i.status === "done" ? "line-through" : "none", color: i.status === "done" ? "var(--muted)" : "var(--ink)" }}>{i.description}</div>
                <div className="sub">{[i.contact, i.property, i.due ? `Due ${formatDate(i.due)}` : null].filter(Boolean).join(" · ")}</div>
              </div>
              {i.status === "open" ? (
                <div className="row" style={{ gap: 6 }}>
                  <button className="btn sm primary" disabled={busyId === i.id} onClick={() => void setStatus(i.id, "done")}><CheckCircle2 size={14} /> Done</button>
                  <button className="btn sm ghost" disabled={busyId === i.id} onClick={() => void setStatus(i.id, "cancelled")}>Dismiss</button>
                </div>
              ) : (
                <button className="btn sm" disabled={busyId === i.id} onClick={() => void setStatus(i.id, "open")}>Reopen</button>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
