"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { CategoryChip, FlagChip, HintChip, formatTime, scoreClass } from "@/lib/format";
import { get } from "@/lib/api";
import type { ThreadSummary } from "@/lib/types";
import { useUser } from "@/lib/user-context";

export default function InboxPage() {
  const { activeId } = useUser();
  const [threads, setThreads] = useState<ThreadSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!activeId) return;
    let cancelled = false;
    (async () => {
      try {
        const r = await get<{ threads: ThreadSummary[] }>(`/emails/inbox/${activeId}`);
        if (!cancelled) setThreads(r.threads);
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
        <h2>No agent account yet</h2>
        <p>Connect your Gmail above to get started.</p>
      </div>
    );

  if (threads === null) return <div className="empty">Loading inbox…</div>;
  if (error) return <div className="error-banner">{error}</div>;
  if (threads.length === 0)
    return (
      <div className="empty">
        <h2>Inbox is empty</h2>
        <p>Use “Sync Gmail” then “Run AI” to process your emails.</p>
      </div>
    );

  return (
    <div className="thread-list">
      {threads.map((t) => (
        <Link key={t.id} href={`/thread/${t.id}`} className="thread-row">
          <div className="row-top">
            <span className={`score ${scoreClass(t.priority_score)}`}>
              {t.priority_score ?? "–"}
            </span>
            <span className="subject">{t.subject || "(no subject)"}</span>
            <CategoryChip category={t.category} />
            {t.flags?.slice(0, 2).map((f) => (
              <FlagChip key={f} flag={f} />
            ))}
          </div>
          <div className="meta">
            <span>{t.emails} emails</span>
            <span>·</span>
            <span>{formatTime(t.last_activity_at)}</span>
          </div>
          {t.pipeline_hints?.length > 0 && (
            <div className="badge-row">
              {t.pipeline_hints.slice(0, 3).map((h) => (
                <HintChip key={h} hint={h} />
              ))}
            </div>
          )}
          {t.summary && <div className="summary">{t.summary}</div>}
        </Link>
      ))}
    </div>
  );
}