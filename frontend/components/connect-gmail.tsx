"use client";

import { useSearchParams } from "next/navigation";
import { useState } from "react";

import { useUser } from "@/lib/user-context";

export function ConnectGmail() {
  const { users, connectGmail } = useUser();
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
    <>
      {connected && (
        <div className="error-banner" style={{ background: "var(--ok-weak)", borderColor: "#bbf7d0", color: "var(--ok)" }}>
          Connected {connectedEmail ?? "Gmail"} successfully.
        </div>
      )}
      {oauthError && <div className="error-banner">Gmail connection failed: {oauthError}</div>}
      {error && <div className="error-banner">{error}</div>}

      {users.length === 0 && (
        <div className="empty" style={{ marginBottom: 18 }}>
          <h2>Connect your Gmail</h2>
          <p>
            We read and summarize your inbox so you can approve or ignore each
            thread. Read-only access — nothing is sent without your say.
          </p>
          <button className="btn primary" onClick={connect} disabled={busy} style={{ marginTop: 10 }}>
            {busy && <span className="spin" />} Connect Gmail
          </button>
        </div>
      )}
    </>
  );
}