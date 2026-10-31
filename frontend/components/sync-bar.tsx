"use client";

import { useState } from "react";

import { useUser } from "@/lib/user-context";
import type { ProcessStats, SyncStats } from "@/lib/types";

export function SyncBar() {
  const { activeId, syncInbox, processAll, busy, error } = useUser();
  const [notice, setNotice] = useState<string | null>(null);

  async function onSync() {
    if (!activeId) return;
    setNotice(null);
    try {
      const stats: SyncStats = await syncInbox();
      setNotice(
        `Synced ${stats.threads} thread(s), ${stats.emails_added} new email(s), ${stats.errors} error(s).`,
      );
    } catch {
      /* error surfaced in banner */
    }
  }

  async function onProcess() {
    if (!activeId) return;
    setNotice(null);
    try {
      const stats: ProcessStats = await processAll();
      setNotice(
        stats.processed > 0
          ? `AI processed ${stats.processed} email(s), ${stats.errors} error(s).`
          : "No unprocessed emails. Sync first, or there is nothing new.",
      );
    } catch {
      /* error surfaced in banner */
    }
  }

  return (
    <>
      {error && <div className="error-banner">{error}</div>}
      <div className="page-head">
        <div>
          <h1>Dashboard</h1>
          <div className="sub">Your AI-assessed inbox at a glance.</div>
        </div>
        <div style={{ display: "flex", gap: "8px" }}>
          <button className="btn" onClick={onSync} disabled={!activeId || busy}>
            {busy && <span className="spin" />} Sync Gmail
          </button>
          <button
            className="btn primary"
            onClick={onProcess}
            disabled={!activeId || busy}
          >
            {busy && <span className="spin" />} Run AI
          </button>
        </div>
      </div>
      {notice && <div className="sub" style={{ color: "var(--ok)" }}>{notice}</div>}
    </>
  );
}