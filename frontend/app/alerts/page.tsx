"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Bell, Check, ShieldAlert } from "lucide-react";
import { get, put } from "@/lib/api";
import { formatTime } from "@/lib/format";
import type { Preferences } from "@/lib/types";
import { useUser } from "@/lib/user-context";

const TYPE_LABEL: Record<string, string> = { hot_lead: "Hot lead", urgent: "Urgent", closing: "Closing", complaint: "Complaint" };

export default function AlertsPage() {
  const { activeId, notifications, unreadCount, markRead } = useUser();
  const [prefs, setPrefs] = useState<Preferences | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!activeId) return;
    let cancelled = false;
    get<Preferences>(`/preferences/${activeId}`).then((p) => { if (!cancelled) setPrefs(p); }).catch((e) => { if (!cancelled) setError(e instanceof Error ? e.message : String(e)); });
    return () => { cancelled = true; };
  }, [activeId]);

  async function toggleAutopilot() {
    if (!activeId || !prefs) return;
    setSaving(true); setError(null);
    try { setPrefs(await put<Preferences>(`/preferences/${activeId}`, { autopilot: !prefs.auto_features.autopilot })); }
    catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setSaving(false); }
  }

  if (!activeId) return <div className="empty"><h2>No account</h2><p>Connect to receive alerts.</p></div>;
  const autopilotOn = Boolean(prefs?.auto_features.autopilot);

  return (
    <div className="stack">
      <div className="page-head">
        <div>
          <h1>Alerts</h1>
          <div className="sub">{unreadCount} unread · {notifications.length} total notifications.</div>
        </div>
      </div>

      {error && <div className="error-banner">{error}</div>}

      <div className="card card-pad autopilot-card">
        <div className="row" style={{ alignItems: "flex-start", gap: 12 }}>
          <ShieldAlert size={18} color={autopilotOn ? "var(--primary)" : "var(--muted)"} />
          <div>
            <div style={{ fontWeight: 700 }}>Auto-Pilot</div>
            <p className="muted-note">When enabled, low-risk replies may be sent automatically based on your rules and confidence threshold. Sensitive or flagged emails are always held for review.</p>
          </div>
        </div>
        <button className={`btn ${autopilotOn ? "ghost" : "primary"}`} onClick={() => void toggleAutopilot()} disabled={!prefs || saving}>
          {saving ? "Saving…" : autopilotOn ? "Turn off" : "Enable"}
        </button>
      </div>

      <div>
        <div className="label">Notifications</div>
        {notifications.length === 0 ? (
          <div className="empty"><h2>No alerts yet</h2><p>Hot leads, deadlines, complaints, and urgent items will appear here.</p></div>
        ) : (
          <div className="thread-list">
            {notifications.map((n) => (
              <div key={n.id} className={`note ${n.is_read ? "" : "unread"}`}>
                <div className="row-top">
                  <span className={`chip ${/hot_lead|urgent|complaint/.test(n.type) ? "hot" : "warn"}`}>{TYPE_LABEL[n.type] ?? n.type}</span>
                  <span className="subject">{n.title}</span>
                  <span className="time">{formatTime(n.created_at)}</span>
                </div>
                {n.body && <div className="summary">{n.body}</div>}
                <div className="note-actions">
                  {n.thread_id && <Link className="back-link" href={`/thread/${n.thread_id}`}>Open thread</Link>}
                  {!n.is_read && <button className="btn sm" onClick={() => void markRead(n.id)}><Check size={14} /> Mark read</button>}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
