"use client";

import { useState } from "react";

import { useUser } from "@/lib/user-context";
import type { ProcessStats, SyncStats } from "@/lib/types";

export function SyncBar() {
  const { activeId, syncInbox, processAll, busy, error } = useUser();
  const [notice, setNotice] = useState<string | null>(null);
  const [running, setRunning] = useState<"sync" | "process" | null>(null);

  async function onSync() {
    if (!activeId) return;
    setNotice(null);
    setRunning("sync");
    try {
      const stats: SyncStats = await syncInbox();
      setNotice(
        `Synced ${stats.threads} thread(s), ${stats.emails_added} new email(s), ${stats.errors} error(s).`,
      );
    } catch {
      /* error surfaced in banner */
    } finally {
      setRunning(null);
    }
  }

  async function onProcess() {
    if (!activeId) return;
    setNotice("Processing emails with AI...");
    setRunning("process");
    try {
      const stats: ProcessStats = await processAll();
      setNotice(
        stats.processed > 0 || stats.errors > 0
          ? `AI reviewed ${stats.processed} email(s), ${stats.errors} error(s)${stats.pending ? `, ${stats.pending} pending` : ""}.`
          : "No unprocessed emails. Sync first, or there is nothing new.",
      );
    } catch {
      setNotice(null);
      /* error surfaced in banner */
    } finally {
      setRunning(null);
    }
  }

  return (
    <>
      {error && <div className="error-banner">{error}</div>}
      <div className="sync-bar">
        <button className="btn" onClick={onSync} disabled={!activeId || busy}>
          {running === "sync" && <span className="spin" />} Sync Gmail
        </button>
        <button
          className="btn primary"
          onClick={onProcess}
          disabled={!activeId || busy}
        >
          {running === "process" && <span className="spin" />} Run AI
        </button>
      </div>
      {notice && <div className="sub" style={{ color: "var(--ok)" }}>{notice}</div>}
    </>
  );
}