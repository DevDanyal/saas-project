"use client";

import { useEffect, useState } from "react";
import { Check, CreditCard } from "lucide-react";
import { get, post } from "@/lib/api";
import type { BillingUsage, PlanLimits, Price, Subscription } from "@/lib/types";
import { useUser } from "@/lib/user-context";

export default function BillingPage() {
  const { activeId } = useUser();
  const [subscription, setSubscription] = useState<Subscription | null>(null);
  const [prices, setPrices] = useState<Price[]>([]);
  const [usage, setUsage] = useState<BillingUsage | null>(null);
  const [loadedFor, setLoadedFor] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [checkoutLoading, setCheckoutLoading] = useState<string | null>(null);

  useEffect(() => {
    if (!activeId) return;
    let cancelled = false;
    (async () => {
      try {
        const [sub, pricesData, limitsData] = await Promise.all([
          get<Subscription>(`/billing/subscription/${activeId}`),
          get<{ prices: Price[] }>("/billing/prices"),
          get<{ plan: string; limits: PlanLimits; usage: BillingUsage; can_process: boolean }>(`/billing/limits/${activeId}`),
        ]);
        if (cancelled) return;
        setSubscription(sub);
        setPrices(pricesData.prices || []);
        setUsage(limitsData.usage);
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      } finally {
        if (!cancelled) setLoadedFor(activeId);
      }
    })();
    return () => { cancelled = true; };
  }, [activeId]);

  async function startCheckout(priceId: string) {
    if (!activeId) return;
    setCheckoutLoading(priceId);
    try {
      const { url } = await post<{ url: string }>(`/billing/checkout/${activeId}`, { price_id: priceId });
      window.location.assign(url);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setCheckoutLoading(null);
    }
  }

  async function openPortal() {
    if (!activeId) return;
    try {
      const { url } = await post<{ url: string }>(`/billing/portal/${activeId}`, {});
      window.location.assign(url);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  if (!activeId) return <div className="empty"><h2>No account</h2><p>Select an account to manage billing.</p></div>;
  if (loadedFor !== activeId) return <div className="card card-pad sub">Loading billing?</div>;

  const currentPlan = (subscription?.plan ?? "free").toLowerCase();
  const usagePercent = usage && usage.limit > 0 ? Math.min(100, Math.round((usage.used / usage.limit) * 100)) : 0;

  return (
    <div className="stack">
      <div className="page-head">
        <div>
          <h1>Billing</h1>
          <div className="sub">Manage your subscription, usage, and plan limits.</div>
        </div>
        {subscription?.status === "active" && <button className="btn" onClick={() => void openPortal()}><CreditCard size={14} /> Manage subscription</button>}
      </div>

      {error && <div className="error-banner">{error}</div>}

      <div className="grid-3">
        <div className="card card-pad">
          <div className="label">Current plan</div>
          <div style={{ fontSize: 22, fontWeight: 700, letterSpacing: "-.02em", textTransform: "capitalize" }}>{currentPlan}</div>
          <div className="row" style={{ marginTop: 8 }}>
            <span className={`chip ${currentPlan === "pro" || currentPlan === "team" ? "primary" : "neutral"}`}>{currentPlan}</span>
            <span className={`chip ${subscription?.status === "active" ? "ok" : "warn"}`}>{subscription?.status ?? "inactive"}</span>
          </div>
          {subscription?.current_period_end && <div className="sub" style={{ marginTop: 8 }}>Renews {new Date(subscription.current_period_end).toLocaleDateString()}</div>}
        </div>

        <div className="card card-pad" style={{ gridColumn: "span 2" }}>
          <div className="label">Usage this month</div>
          {!usage ? (
            <div className="sub">Usage data unavailable.</div>
          ) : usage.limit === -1 ? (
            <div>
              <div style={{ fontSize: 22, fontWeight: 700 }}>{usage.used} <span className="sub" style={{ fontSize: 14 }}>emails processed</span></div>
              <div className="sub" style={{ marginTop: 4 }}>Unlimited emails included in your plan.</div>
            </div>
          ) : (
            <div>
              <div className="row" style={{ justifyContent: "space-between" }}>
                <div style={{ fontSize: 22, fontWeight: 700 }}>{usage.used} <span className="sub" style={{ fontSize: 14 }}>/ {usage.limit} emails</span></div>
                <div className="sub" style={{ fontWeight: 600 }}>{usagePercent}% used</div>
              </div>
              <div style={{ height: 10, background: "var(--bg-subtle)", borderRadius: 999, overflow: "hidden", marginTop: 10, border: "1px solid var(--border)" }}>
                <div style={{ height: "100%", width: `${usagePercent}%`, background: usage.remaining > 0 ? "var(--primary)" : "var(--danger)", borderRadius: 999, transition: "width .3s" }} />
              </div>
              <div className="sub" style={{ marginTop: 6 }}>{usage.remaining} emails remaining this month.</div>
            </div>
          )}
        </div>
      </div>

      <div>
        <div className="label" style={{ marginBottom: 2 }}>Plans</div>
        <div className="sub" style={{ marginBottom: 10 }}>Choose the plan that fits your inbox volume.</div>
        {prices.length === 0 ? (
          <div className="empty"><h2>Plans unavailable</h2><p>Billing plans could not be loaded right now.</p></div>
        ) : (
          <div className="grid-3">
            {prices.map((p) => {
              const name = p.name.toLowerCase();
              const isCurrent = name === currentPlan;
              const features = [
                `${name === "free" ? "200" : "5,000"} emails / month`,
                `${name === "free" ? "Limited" : "Unlimited"} smart replies`,
                `Auto-pilot: ${name === "free" ? "No" : "Yes"}`,
                `Calendar sync: ${name === "free" ? "No" : "Yes"}`,
                ...(name === "team" ? ["Shared team inbox", "Team reports & roles"] : []),
              ];
              return (
                <div key={p.name} className={`card card-pad ${isCurrent ? "ai-brief" : ""}`} style={{ display: "flex", flexDirection: "column", minHeight: 300 }}>
                  <div className="row" style={{ justifyContent: "space-between" }}>
                    <div style={{ fontSize: 18, fontWeight: 700, textTransform: "capitalize" }}>{p.name}</div>
                    {isCurrent && <span className="chip primary">Current</span>}
                  </div>
                  <div style={{ marginTop: 8 }}>
                    <span style={{ fontSize: 34, fontWeight: 750, letterSpacing: "-.03em" }}>${p.monthly_price}</span>
                    <span className="sub"> / month</span>
                  </div>
                  <ul style={{ listStyle: "none", padding: 0, margin: "14px 0 0", display: "grid", gap: 8, flex: 1 }}>
                    {features.map((f) => (
                      <li key={f} className="row" style={{ alignItems: "flex-start", gap: 8, fontSize: 13.5, color: "var(--ink-soft)", flexWrap: "nowrap" }}>
                        <Check size={15} color="var(--primary)" style={{ marginTop: 2, flex: "0 0 auto" }} />
                        <span style={{ minWidth: 0, overflowWrap: "anywhere" }}>{f}</span>
                      </li>
                    ))}
                  </ul>
                  <button className={`btn ${isCurrent ? "ghost" : "primary"}`} onClick={() => void startCheckout(p.price_id)} disabled={isCurrent || checkoutLoading === p.price_id} style={{ width: "100%", marginTop: 16 }}>
                    {checkoutLoading === p.price_id ? "Redirecting?" : isCurrent ? "Current plan" : p.monthly_price === 0 ? "Select Free" : `Upgrade to ${p.name}`}
                  </button>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
