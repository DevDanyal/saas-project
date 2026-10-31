"use client";

import { useEffect, useState } from "react";

import { get, post } from "@/lib/api";
import type { Subscription, Price, BillingUsage, PlanLimits } from "@/lib/types";
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
          get<{
            plan: string;
            limits: PlanLimits;
            usage: BillingUsage;
            can_process: boolean;
          }>(`/billing/limits/${activeId}`),
        ]);
        if (cancelled) return;
        setSubscription(sub);
        setPrices(pricesData.prices);
        setUsage(limitsData.usage);
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      } finally {
        if (!cancelled) setLoadedFor(activeId);
      }
    })();
    return () => {
      cancelled = true;
    };
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

  if (!activeId)
    return (
      <div className="empty">
        <h2>No agent account</h2>
        <p>Select an account to manage billing.</p>
      </div>
    );

  if (loadedFor !== activeId) return <div className="empty">Loading billing…</div>;

  const currentPlan = subscription?.plan ?? "free";

  return (
    <div>
      <div className="page-head">
        <div>
          <h1>Billing</h1>
          <div className="sub">Manage your plan and subscription.</div>
        </div>
      </div>

      {error && <div className="error-banner">{error}</div>}

      <div className="card" style={{ marginBottom: 16 }}>
        <div className="label">Current Plan</div>
        <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
          <span className={`chip ${currentPlan === "pro" || currentPlan === "team" ? "primary" : "neutral"}`}>
            {currentPlan.charAt(0).toUpperCase() + currentPlan.slice(1)}
          </span>
          <span className={`chip ${subscription?.status === "active" ? "ok" : "warn"}`}>
            {subscription?.status ?? "inactive"}
          </span>
          {subscription?.current_period_end && (
            <span className="chip neutral">
              Renews: {new Date(subscription.current_period_end).toLocaleDateString()}
            </span>
          )}
          {subscription?.status === "active" && (
            <button className="btn" onClick={openPortal} style={{ marginLeft: "auto" }}>
              Manage Subscription
            </button>
          )}
        </div>
      </div>

      <div className="card" style={{ marginBottom: 16 }}>
        <div className="label">Usage This Month</div>
        {usage && usage.limit > 0 && (
          <div style={{ marginTop: 8 }}>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
              <span>Emails processed</span>
              <span>{usage.used} / {usage.limit}</span>
            </div>
            <div
              className="progress-bar"
              style={{
                height: 8,
                background: "var(--border)",
                borderRadius: 4,
                overflow: "hidden",
              }}
            >
              <div
                className="progress-fill"
                style={{
                  height: "100%",
                  width: `${Math.min(100, (usage.used / usage.limit) * 100)}%`,
                  background: usage.remaining > 0 ? "var(--primary)" : "var(--danger)",
                  transition: "width 0.3s",
                }}
              />
            </div>
            <div className="sub" style={{ marginTop: 4 }}>
              {usage.remaining} emails remaining this month
            </div>
          </div>
        )}
        {usage && usage.limit === -1 && (
          <div className="sub" style={{ marginTop: 8 }}>
            Unlimited emails (Pro/Team plan)
          </div>
        )}
      </div>

      <h2 className="section-title" style={{ marginTop: 24 }}>
        Available Plans
      </h2>

      <div className="price-grid">
        {prices.map((p) => (
          <div
            key={p.name}
            className={`price-card ${p.name.toLowerCase() === currentPlan ? "current" : ""}`}
          >
            <div className="price-name">{p.name}</div>
            <div className="price-amount">
              ${p.monthly_price}
              <span className="price-period">/mo</span>
            </div>
            <ul className="price-features">
              <li>
                {p.name === "free" ? "200" : "5,000"} emails/month
              </li>
              <li>
                {p.name === "free" ? "Limited" : "Unlimited"} smart replies
              </li>
              <li>Auto-pilot: {p.name === "free" ? "No" : "Yes"}</li>
              <li>Calendar sync: {p.name === "free" ? "No" : "Yes"}</li>
              {p.name === "team" && <li>Team/shared inbox</li>}
              {p.name === "team" && <li>Team reports</li>}
            </ul>
            <button
              className={`btn ${p.name.toLowerCase() === currentPlan ? "secondary" : "primary"}`}
              onClick={() => startCheckout(p.price_id)}
              disabled={checkoutLoading === p.price_id || p.name.toLowerCase() === currentPlan}
              style={{ width: "100%", marginTop: 12 }}
            >
              {checkoutLoading === p.price_id
                ? "Redirecting…"
                : p.name.toLowerCase() === currentPlan
                ? "Current Plan"
                : p.monthly_price === 0
                ? "Select Free"
                : `Upgrade to ${p.name}`}
            </button>
          </div>
        ))}
      </div>

      <style jsx>{`
        .price-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
          gap: 16px;
          margin-top: 12px;
        }
        .price-card {
          border: 1px solid var(--border);
          border-radius: 12px;
          padding: 20px;
          background: var(--card);
          transition: border-color 0.2s, box-shadow 0.2s;
        }
        .price-card.current {
          border-color: var(--primary);
          box-shadow: 0 0 0 2px var(--primary-weak);
        }
        .price-name {
          font-weight: 600;
          font-size: 16px;
        }
        .price-amount {
          font-size: 32px;
          font-weight: 700;
          margin: 8px 0;
        }
        .price-period {
          font-size: 16px;
          font-weight: 400;
          color: var(--muted);
        }
        .price-features {
          list-style: none;
          padding: 0;
          margin: 16px 0 0;
        }
        .price-features li {
          padding: 6px 0;
          font-size: 14px;
          color: var(--muted);
        }
        .progress-bar {
          width: 100%;
        }
      `}</style>
    </div>
  );
}