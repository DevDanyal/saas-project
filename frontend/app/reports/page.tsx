"use client";

import { useEffect, useState } from "react";
import { get } from "@/lib/api";
import type { Team, TeamReport } from "@/lib/types";
import { useUser } from "@/lib/user-context";

export default function ReportsPage() {
  const { activeId } = useUser();
  const [teams, setTeams] = useState<Team[]>([]);
  const [selectedTeamId, setSelectedTeamId] = useState<string | null>(null);
  const [report, setReport] = useState<TeamReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [reportLoading, setReportLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!activeId) return;
    let cancelled = false;
    (async () => {
      try {
        const data = await get<{ teams: Team[] }>("/teams");
        if (cancelled) return;
        setTeams(data.teams || []);
        setSelectedTeamId((prev) => prev ?? data.teams?.[0]?.id ?? null);
      } catch (e) { if (!cancelled) setError(e instanceof Error ? e.message : String(e)); }
      finally { if (!cancelled) setLoading(false); }
    })();
    return () => { cancelled = true; };
  }, [activeId]);

  useEffect(() => {
    if (!selectedTeamId) return;
    let cancelled = false;
    (async () => {
      setReportLoading(true);
      try {
        const data = await get<TeamReport>(`/reports/team/${selectedTeamId}?days=30`);
        if (!cancelled) setReport(data);
      } catch (e) { if (!cancelled) setError(e instanceof Error ? e.message : String(e)); }
      finally { if (!cancelled) setReportLoading(false); }
    })();
    return () => { cancelled = true; };
  }, [selectedTeamId]);

  if (!activeId) return <div className="empty"><h2>No account</h2><p>Select an account to view reports.</p></div>;
  if (loading) return <div className="card card-pad sub">Loading reports?</div>;

  if (teams.length === 0) {
    return (
      <div className="stack">
        <div className="page-head"><div><h1>Team Reports</h1><div className="sub">View team activity and performance metrics.</div></div></div>
        <div className="empty"><h2>No teams yet</h2><p>Create a team first to see reports.</p></div>
      </div>
    );
  }

  return (
    <div className="stack">
      <div className="page-head">
        <div>
          <h1>Team Reports</h1>
          <div className="sub">Activity and performance for the last 30 days.</div>
        </div>
        <select className="select" value={selectedTeamId ?? ""} onChange={(e) => setSelectedTeamId(e.target.value)} style={{ minWidth: 220, maxWidth: 320 }}>
          {teams.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
        </select>
      </div>

      {error && <div className="error-banner">{error}</div>}

      {reportLoading ? (
        <div className="card card-pad sub">Generating report?</div>
      ) : !report ? (
        <div className="empty"><h2>No data</h2><p>Select a team to generate a report.</p></div>
      ) : (
        <div className="stack">
          <div className="grid-4">
            <div className="kpi"><div className="kpi-label">Emails processed</div><div className="kpi-value">{report.emails_processed?.total ?? 0}</div><div className="kpi-meta">Last 30 days</div></div>
            <div className="kpi"><div className="kpi-label">Actions created</div><div className="kpi-value">{report.actions_created?.total ?? 0}</div><div className="kpi-meta">Extracted tasks</div></div>
            <div className="kpi"><div className="kpi-label">Categories</div><div className="kpi-value">{Object.keys(report.categories ?? {}).length}</div><div className="kpi-meta">Active categories</div></div>
            <div className="kpi"><div className="kpi-label">High priority</div><div className="kpi-value">{report.priority_distribution?.high ?? 0}</div><div className="kpi-meta">Score ? 80</div></div>
          </div>

          <div className="grid-2">
            <div className="card card-pad">
              <div className="label">Emails by member</div>
              {Object.keys(report.emails_processed?.by_member ?? {}).length === 0 ? <div className="sub">No data.</div> : (
                <div className="stack" style={{ gap: 8 }}>
                  {Object.entries(report.emails_processed?.by_member ?? {}).map(([email, count]) => (
                    <div key={email} className="row" style={{ justifyContent: "space-between", borderBottom: "1px solid var(--border)", paddingBottom: 6 }}>
                      <span style={{ fontSize: 13.5, overflowWrap: "anywhere", minWidth: 0 }}>{email}</span>
                      <strong>{count as number}</strong>
                    </div>
                  ))}
                </div>
              )}
            </div>
            <div className="card card-pad">
              <div className="label">Actions by member</div>
              {Object.keys(report.actions_created?.by_member ?? {}).length === 0 ? <div className="sub">No data.</div> : (
                <div className="stack" style={{ gap: 8 }}>
                  {Object.entries(report.actions_created?.by_member ?? {}).map(([email, count]) => (
                    <div key={email} className="row" style={{ justifyContent: "space-between", borderBottom: "1px solid var(--border)", paddingBottom: 6 }}>
                      <span style={{ fontSize: 13.5, overflowWrap: "anywhere", minWidth: 0 }}>{email}</span>
                      <strong>{count as number}</strong>
                    </div>
                  ))}
                </div>
              )}
            </div>
            <div className="card card-pad">
              <div className="label">Categories</div>
              {Object.keys(report.categories ?? {}).length === 0 ? <div className="sub">No data.</div> : (
                <div className="stack" style={{ gap: 8 }}>
                  {Object.entries(report.categories ?? {}).map(([cat, count]) => (
                    <div key={cat} className="row" style={{ justifyContent: "space-between" }}><span className="chip neutral" style={{ textTransform: "capitalize" }}>{cat}</span><strong>{count as number}</strong></div>
                  ))}
                </div>
              )}
            </div>
            <div className="card card-pad">
              <div className="label">Priority distribution</div>
              <div className="stack" style={{ gap: 8 }}>
                <div className="row" style={{ justifyContent: "space-between" }}><span className="chip hot">High (?80)</span><strong>{report.priority_distribution?.high ?? 0}</strong></div>
                <div className="row" style={{ justifyContent: "space-between" }}><span className="chip warn">Medium (50-79)</span><strong>{report.priority_distribution?.medium ?? 0}</strong></div>
                <div className="row" style={{ justifyContent: "space-between" }}><span className="chip neutral">Low (&lt;50)</span><strong>{report.priority_distribution?.low ?? 0}</strong></div>
              </div>
              <div className="label" style={{ marginTop: 14 }}>Notifications</div>
              {Object.keys(report.notifications ?? {}).length === 0 ? <div className="sub">No data.</div> : (
                <div className="stack" style={{ gap: 8 }}>
                  {Object.entries(report.notifications ?? {}).map(([type, count]) => (
                    <div key={type} className="row" style={{ justifyContent: "space-between" }}><span style={{ textTransform: "capitalize", fontSize: 13.5 }}>{type.replace(/_/g, " ")}</span><strong>{count as number}</strong></div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
