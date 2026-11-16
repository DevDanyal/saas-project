"use client";

import { useSearchParams } from "next/navigation";
import { useState } from "react";
import { useUser } from "@/lib/user-context";

export function ConnectGmail() {
  const { user, connectGmail } = useUser();
  const params = useSearchParams();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const connected = params.get("connected");
  const connectedEmail = params.get("email");
  const oauthError = params.get("error");

  async function connect() {
    setBusy(true);
    setError(null);
    try {
      await connectGmail();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setBusy(false);
    }
  }

  return (
    <div className="stack" style={{ marginBottom: 12 }}>
      {connected && (
        <div className="notice-banner">Gmail connected{connectedEmail ? `: ${connectedEmail}` : ""}. Sync to pull your latest conversations.</div>
      )}
      {oauthError && <div className="error-banner">Gmail connection failed: {oauthError}</div>}
      {error && <div className="error-banner">{error}</div>}

      {!user?.gmail_connected && (
        <div className="card card-pad" style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, flexWrap: "wrap", background: "linear-gradient(135deg,#f8f1e5,#fffdfa)" }}>
          <div>
            <div style={{ fontWeight: 700, fontSize: 15 }}>Connect Gmail to activate your Smart Inbox</div>
            <div className="sub">We read and summarize conversations to prioritize leads, extract actions, and draft replies. Nothing is sent without your approval.</div>
          </div>
          <button className="btn primary" onClick={() => void connect()} disabled={busy}>
            {busy ? <span className="spin" /> : null} Connect Gmail
          </button>
        </div>
      )}
    </div>
  );
}

