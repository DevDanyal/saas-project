"use client";

import { useEffect, useState } from "react";

import { get } from "@/lib/api";
import type { Digest } from "@/lib/types";
import { useUser } from "@/lib/user-context";

function Section({ title, items }: { title: string; items: string[] }) {
  if (!items || items.length === 0) return null;
  return (
    <div className="card" style={{ marginTop: 12 }}>
      <div className="label">{title}</div>
      <ul className="section-list">
        {items.map((item, i) => (
          <li key={i}>{item}</li>
        ))}
      </ul>
    </div>
  );
}

export default function DigestPage() {
  const { activeId } = useUser();
  const [digest, setDigest] = useState<Digest | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!activeId) return;
    let cancelled = false;
    (async () => {
      try {
        const d = await get<Digest>(`/emails/digest/${activeId}`);
        if (!cancelled) setDigest(d);
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
        <p>Select an account to build its morning brief.</p>
      </div>
    );

  if (digest === null) return <div className="empty">Building your morning brief…</div>;
  if (error) return <div className="error-banner">{error}</div>;

  return (
    <div>
      <div className="page-head">
        <div>
          <h1>Daily Digest</h1>
          <div className="sub">
            {digest?.threads_in_window ?? 0} threads in the last{" "}
            {digest?.window_hours ?? 24}h · {digest?.actions_in_window ?? 0} open actions
          </div>
        </div>
      </div>

      {(!digest || (!digest.brief && !digest.sections && digest.threads_in_window === 0)) ? (
        <div className="empty">
          <h2>No activity yet</h2>
          <p>Sync and run AI on some emails, then come back for your brief.</p>
        </div>
      ) : (
        <>
          {digest.brief && <div className="digest-brief">{digest.brief}</div>}
          <Section title="Hot leads" items={digest?.sections?.hot_leads ?? []} />
          <Section title="Closings & deadlines" items={digest?.sections?.closings ?? []} />
          <Section title="Overdue follow-ups" items={digest?.sections?.follow_ups ?? []} />
          <Section title="Other" items={digest?.sections?.other ?? []} />
        </>
      )}
    </div>
  );
}