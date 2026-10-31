"use client";

import { useState } from "react";

import { post } from "@/lib/api";
import { formatTime } from "@/lib/format";
import type { Draft } from "@/lib/types";

type SendResult = {
  draft_id: string;
  status: string;
  sent_message_id: string | null;
};

export function DraftBox({ draft, onSent }: { draft: Draft; onSent: () => void }) {
  const sent = draft.status === "sent";
  const [text, setText] = useState(draft.text);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const dirty = text.trim() !== draft.text.trim();

  async function send() {
    setSending(true);
    setError(null);
    try {
      await post<SendResult>(`/emails/drafts/${draft.id}/send`, { text });
      onSent();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="ai-box" style={{ marginTop: 12 }}>
      <div className="label">
        AI draft reply{" "}
        {draft.tone && <span>· tone: {draft.tone}</span>}
        {sent && <span> · sent {formatTime(draft.sent_at ?? null)}</span>}
      </div>

      {sent ? (
        <div className="body">{draft.text}</div>
      ) : (
        <textarea
          className="draft-input"
          value={text}
          onChange={(e) => setText(e.target.value)}
          rows={Math.min(12, Math.max(4, text.split("\n").length + 1))}
        />
      )}

      {draft.auto_decision && (
        <div className="auto-note">
          <span className={`chip ${draft.auto_decision.send ? "ok" : "warm"}`}>
            {draft.auto_decision.send
              ? `Auto-Pilot approved · ${Math.round(
                  draft.auto_decision.confidence * 100,
                )}%`
              : "Held for your review"}
          </span>
          {draft.auto_decision.reason && (
            <span className="sub"> {draft.auto_decision.reason}</span>
          )}
        </div>
      )}

      {error && <div className="error-banner" style={{ marginTop: 10 }}>{error}</div>}

      {!sent && (
        <div className="draft-actions">
          <button className="btn primary" onClick={send} disabled={sending || !text.trim()}>
            {sending ? "Sending…" : dirty ? "Send edited reply" : "Send reply"}
          </button>
          {dirty && (
            <button className="btn" onClick={() => setText(draft.text)} disabled={sending}>
              Reset
            </button>
          )}
        </div>
      )}
    </div>
  );
}
