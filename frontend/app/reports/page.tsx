"use client";

import { useEffect, useState } from "react";

import { get } from "@/lib/api";
import { useUser } from "@/lib/user-context";
import type { Team, TeamReport } from "@/lib/types";

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
        setTeams(data.teams);
        setSelectedTeamId((prev) => prev ?? data.teams[0]?.id ?? null);
        setReportLoading(true);
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [activeId]);

  useEffect(() => {
    if (!selectedTeamId) return;
    let cancelled = false;
    (async () => {
      try {
        const data = await get<TeamReport>(`/reports/team/${selectedTeamId}?days=30`);
        if (!cancelled) setReport(data);
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      } finally {
        if (!cancelled) setReportLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [selectedTeamId]);

  if (!activeId)
    return (
      <div className="empty">
        <h2>No agent account</h2>
        <p>Select an account to view reports.</p>
      </div>
    );

  if (loading) return <div className="empty">Loading…</div>;

  if (teams.length === 0) {
    return (
      <div>
        <div className="page-head">
          <div>
            <h1>Team Reports</h1>
            <div className="sub">View team activity and performance metrics.</div>
          </div>
        </div>
        <div className="empty">
          <h2>No teams yet</h2>
          <p>Create a team first to see reports.</p>
        </div>
      </div>
    );
  }

  return (
    <div>
      <div className="page-head">
        <div>
          <h1>Team Reports</h1>
          <div className="sub">View team activity and performance metrics.</div>
        </div>
        <select
          value={selectedTeamId ?? ""}
          onChange={(e) => {
            setReportLoading(true);
            setSelectedTeamId(e.target.value);
          }}
          className="role-select"
          style={{ minWidth: 250 }}
        >
          {teams.map((t) => (
            <option key={t.id} value={t.id}>
              {t.name}
            </option>
          ))}
        </select>
      </div>

      {error && <div className="error-banner">{error}</div>}

      {reportLoading ? (
        <div className="empty">Generating report…</div>
      ) : report ? (
        <div className="report-grid">
          <div className="report-card">
            <h3>Emails Processed</h3>
            <div className="metric">{report.emails_processed?.total ?? 0}</div>
            <div className="sub-metrics">
              {Object.entries(report.emails_processed?.by_member ?? {}).map(([email, count]) => (
                <div key={email} className="sub-metric">
                  <span>{email}</span>
                  <span>{count as number}</span>
                </div>
              ))}
            </div>
          </div>

          <div className="report-card">
            <h3>Actions Created</h3>
            <div className="metric">{report.actions_created?.total ?? 0}</div>
            <div className="sub-metrics">
              {Object.entries(report.actions_created?.by_member ?? {}).map(([email, count]) => (
                <div key={email} className="sub-metric">
                  <span>{email}</span>
                  <span>{count as number}</span>
                </div>
              ))}
            </div>
          </div>

          <div className="report-card">
            <h3>Categories</h3>
            <div className="metric">{Object.keys(report.categories ?? {}).length}</div>
            <div className="sub-metrics">
              {Object.entries(report.categories ?? {}).map(([cat, count]) => (
                <div key={cat} className="sub-metric">
                  <span>{cat}</span>
                  <span>{count as number}</span>
                </div>
              ))}
            </div>
          </div>

          <div className="report-card">
            <h3>Priority</h3>
            <div className="metric">{report.priority_distribution?.high ?? 0} high</div>
            <div className="sub-metrics">
              <div className="sub-metric"><span>High (&ge;80)</span><span>{report.priority_distribution?.high ?? 0}</span></div>
              <div className="sub-metric"><span>Medium (50-79)</span><span>{report.priority_distribution?.medium ?? 0}</span></div>
              <div className="sub-metric"><span>{"Low (<50)"}</span><span>{report.priority_distribution?.low ?? 0}</span></div>
            </div>
          </div>

          <div className="report-card" style={{ gridColumn: "1 / -1" }}>
            <h3>Notifications</h3>
            <div className="sub-metrics" style={{ flexWrap: "wrap" }}>
              {Object.entries(report.notifications ?? {}).map(([type, count]) => (
                <div key={type} className="sub-metric">
                  <span>{type.replace("_", " ")}</span>
                  <span>{count as number}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      ) : (
        <div className="empty">
          <h2>No data</h2>
          <p>Select a team to generate a report.</p>
        </div>
      )}

      <style jsx>{`
        .report-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
          gap: 16px;
          margin-top: 16px;
        }
        .report-card {
          border: 1px solid var(--border);
          border-radius: 12px;
          padding: 20px;
          background: var(--card);
        }
        .report-card h3 {
          margin: 0 0 12px;
          font-size: 14px;
          color: var(--muted);
          text-transform: uppercase;
          letter-spacing: 0.5px;
        }
        .metric {
          font-size: 36px;
          font-weight: 700;
          line-height: 1;
        }
        .sub-metrics {
          display: flex;
          flex-direction: column;
          gap: 6px;
          margin-top: 16px;
        }
        .sub-metric {
          display: flex;
          justify-content: space-between;
          font-size: 13px;
        }
        .sub-metric span:first-child {
          color: var(--muted);
        }
      `}</style>
    </div>
  );
}