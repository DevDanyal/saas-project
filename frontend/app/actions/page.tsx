"use client";

import { useEffect, useState } from "react";

import { formatDate } from "@/lib/format";
import { get } from "@/lib/api";
import type { ActionItem } from "@/lib/types";
import { useUser } from "@/lib/user-context";

export default function ActionsPage() {
  const { activeId } = useUser();
  const [items, setItems] = useState<ActionItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!activeId) return;
    let cancelled = false;
    (async () => {
      try {
        const r = await get<{ action_items: ActionItem[] }>(
          `/emails/action-items/${activeId}`,
        );
        if (!cancelled) setItems(r.action_items);
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [activeId]);

  if (!activeId)
    return (
      <div className="empty">
        <h2>No agent account</h2>
        <p>Select an account to see its extracted action items.</p>
      </div>
    );

  if (items === null) return <div className="empty">Loading action items…</div>;
  if (error) return <div className="error-banner">{error}</div>;

  const sorted = [...items].sort((a, b) =>
    (a.due ?? "9999").localeCompare(b.due ?? "9999"),
  );
  const done = items.filter((i) => i.status === "done");
  const due = sorted.filter((i) => i.status === "open");

  return (
    <div>
      <div className="page-head">
        <div>
          <h1>Action Items</h1>
          <div className="sub">
            {due.length} open · {done.length} done — extracted automatically.
          </div>
        </div>
      </div>

      {due.length === 0 && (
        <div className="empty">
          <h2>Nothing to do</h2>
          <p>No open action items were extracted from your email yet.</p>
        </div>
      )}

      <div className="card" style={{ padding: "6px 0" }}>
        {due.map((i) => (
          <div key={i.id} className="action-item" style={{ padding: "10px 16px" }}>
            <span className={`chip ${i.type === "call" ? "hot" : "warm"}`}>{i.type}</span>
            <span className="desc">
              {i.description}
              {i.contact && <span className="sub"> · {i.contact}</span>}
              {i.property && <span className="sub"> · {i.property}</span>}
            </span>
            <span className="time">due {formatDate(i.due)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}