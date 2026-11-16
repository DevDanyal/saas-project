"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { get, put } from "@/lib/api";
import { formatTime } from "@/lib/format";
import type { Preferences } from "@/lib/types";
import { useUser } from "@/lib/user-context";

const TYPE_LABEL: Record<string, string> = {
  hot_lead: "Hot lead",
  urgent: "Urgent",
  closing: "Closing",
  complaint: "Complaint",
};

export default function AlertsPage() {
  const { activeId, notifications, unreadCount, markRead } = useUser();
  const [prefs, setPrefs] = useState<Preferences | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!activeId) return;
    let cancelled = false;
    (async () => {
      try {
        const p = await get<Preferences>(`/preferences/${activeId}`);
        if (!cancelled) setPrefs(p);
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [activeId]);

  const toggleAutopilot = useCallback(async () => {
    if (!activeId || !prefs) return;
    const next = !prefs.auto_features.autopilot;
    setSaving(true);
    setError(null);
    try {
      const p = await put<Preferences>(`/preferences/${activeId}`, {
        autopilot: next,
      });
      setPrefs(p);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSaving(false);
    }
  }, [activeId, prefs]);

  if (!activeId)
    return (
      <div className="empty">
        <h2>No agent account yet</h2>
        <p>Connect your Gmail to start receiving alerts.</p>
      </div>
    );

  const autopilotOn = Boolean(prefs?.auto_features.autopilot);

  return (
    <div>
      <div className="page-head">
        <div>
          <h1>Alerts</h1>
          <div className="sub">
            {unreadCount} unread · {notifications.length} total
          </div>
        </div>
      </div>

      {error && <div className="error-banner">{error}</div>}

      <div className="card autopilot-card">
        <div>
          <div className="label">Auto-Pilot</div>
          <p className="muted-note">
            When on, the assistant may send low-risk, trusted replies with no
            review. Legal, financial, and flagged emails are always held for you.
          </p>
        </div>
        <button
          className={`btn ${autopilotOn ? "danger" : "primary"}`}
          onClick={toggleAutopilot}
          disabled={!prefs || saving}
        >
          {saving ? "Saving…" : autopilotOn ? "Turn off" : "Turn on"}
        </button>
      </div>

      <h2 className="section-title">Notifications</h2>
      {notifications.length === 0 ? (
        <div className="empty">
          <h2>No alerts yet</h2>
          <p>Hot leads, closings, and at-risk clients will show up here.</p>
        </div>
      ) : (
        <div className="thread-list">
          {notifications.map((n) => (
            <div key={n.id} className={`note ${n.is_read ? "" : "unread"}`}>
              <div className="row-top">
                <span
                  className={`chip ${/hot_lead|urgent|complaint/.test(n.type) ? "hot" : "warm"}`}
                >
                  {TYPE_LABEL[n.type] ?? n.type}
                </span>
                <span className="subject">{n.title}</span>
                <span className="time">{formatTime(n.created_at)}</span>
              </div>
              {n.body && <div className="summary">{n.body}</div>}
              <div className="note-actions">
                {n.thread_id && (
                  <Link className="back-link" href={`/thread/${n.thread_id}`}>
                    Open thread
                  </Link>
                )}
                {!n.is_read && (
                  <button className="btn" onClick={() => markRead(n.id)}>
                    Mark read
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
