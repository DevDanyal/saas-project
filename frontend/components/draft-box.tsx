"use client";

import { useEffect, useState } from "react";

import { del, patch, post } from "@/lib/api";
import { formatTime } from "@/lib/format";
import type { Draft } from "@/lib/types";

type SendResult = {
  draft_id: string;
  status: string;
  sent_message_id: string | null;
  to?: string;
};

export function DraftBox({
  draft,
  recipient,
  onChanged,
}: {
  draft: Draft;
  recipient: string;
  onChanged: () => void;
}) {
  const sent = draft.status === "sent";
  const [text, setText] = useState(draft.text);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setText(draft.text);
  }, [draft.id, draft.text]);

  const dirty = text.trim() !== draft.text.trim();

  async function run(action: () => Promise<unknown>) {
    setBusy(true);
    setError(null);
    try {
      await action();
      onChanged();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  const send = () =>
    run(() => post<SendResult>(`/emails/drafts/${draft.id}/send`, { text }));
  const save = () => run(() => patch(`/emails/drafts/${draft.id}`, { text }));
  const skip = () => run(() => del(`/emails/drafts/${draft.id}`));

  if (sent) {
    return (
      <div className="ai-box" style={{ marginTop: 12 }}>
        <div className="label">
          Reply sent {draft.sent_at && <span>· {formatTime(draft.sent_at)}</span>}
        </div>
        <div className="sent-line">
          <span className="chip ok">Replied to {recipient}</span>
        </div>
        <div className="body" style={{ whiteSpace: "pre-wrap", marginTop: 8 }}>
          {draft.text}
        </div>
      </div>
    );
  }

  return (
    <div className="ai-box" style={{ marginTop: 12 }}>
      <div className="label">
        AI draft reply {draft.tone && <span>· tone: {draft.tone}</span>}
      </div>
      <div className="sub" style={{ marginBottom: 8 }}>
        Edit the reply below, send it, or skip for now to generate a new draft later.
      </div>

      <textarea
        className="draft-input"
        value={text}
        onChange={(e) => setText(e.target.value)}
        rows={Math.min(14, Math.max(5, text.split("\n").length + 1))}
        disabled={busy}
      />

      {draft.auto_decision && (
        <div className="auto-note">
          <span className={`chip ${draft.auto_decision.send ? "ok" : "warm"}`}>
            {draft.auto_decision.send
              ? `Auto-Pilot approved · ${Math.round(draft.auto_decision.confidence * 100)}%`
              : "Held for your review"}
          </span>
          {draft.auto_decision.reason && (
            <span className="sub"> {draft.auto_decision.reason}</span>
          )}
        </div>
      )}

      {error && (
        <div className="error-banner" style={{ marginTop: 10 }}>
          {error}
        </div>
      )}

      <div className="draft-actions">
        <button
          className="btn primary"
          onClick={send}
          disabled={busy || !text.trim()}
        >
          {busy ? "Working..." : "Send reply"}
        </button>
        <button className="btn" onClick={save} disabled={busy || !dirty}>
          Save changes
        </button>
        <button className="btn danger" onClick={skip} disabled={busy}>
          Skip for now
        </button>
      </div>
    </div>
  );
}
