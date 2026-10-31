"use client";

import { useEffect, useState } from "react";

import { get, post, del, patch } from "@/lib/api";
import type { Team, TeamMember } from "@/lib/types";
import { useUser } from "@/lib/user-context";

export default function TeamsPage() {
  const { activeId, users } = useUser();
  const [teams, setTeams] = useState<Team[]>([]);
  const [selectedTeam, setSelectedTeam] = useState<Team | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [newTeamName, setNewTeamName] = useState("");
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState<"admin" | "agent">("agent");

  useEffect(() => {
    if (!activeId) return;
    let cancelled = false;
    (async () => {
      try {
        const data = await get<{ teams: Team[] }>("/teams");
        if (!cancelled) setTeams(data.teams);
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

  async function createTeam() {
    if (!newTeamName.trim()) return;
    setCreating(true);
    try {
      const team = await post<Team>("/teams", { name: newTeamName });
      setTeams((prev) => [...prev, team]);
      setNewTeamName("");
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setCreating(false);
    }
  }

  async function selectTeam(team: Team) {
    try {
      const data = await get<Team>(`/teams/${team.id}`);
      setSelectedTeam(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  async function inviteMember() {
    if (!selectedTeam || !inviteEmail.trim()) return;
    try {
      const user = users.find((u) => u.email === inviteEmail);
      if (!user) {
        setError("User not found. They must sign up first.");
        return;
      }
      await post(`/teams/${selectedTeam.id}/members`, {
        user_id: user.id,
        role: inviteRole,
      });
      await selectTeam(selectedTeam);
      setInviteEmail("");
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  async function removeMember(member: TeamMember) {
    if (!selectedTeam || !confirm(`Remove ${member.name} from team?`)) return;
    try {
      await del(`/teams/${selectedTeam.id}/members/${member.user_id}`);
      await selectTeam(selectedTeam);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  async function updateRole(member: TeamMember, role: "admin" | "agent") {
    if (!selectedTeam) return;
    try {
      await patch(`/teams/${selectedTeam.id}/members/${member.user_id}`, { role });
      await selectTeam(selectedTeam);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  if (!activeId)
    return (
      <div className="empty">
        <h2>No agent account</h2>
        <p>Select an account to manage teams.</p>
      </div>
    );

  if (loading) return <div className="empty">Loading teams…</div>;

  return (
    <div>
      <div className="page-head">
        <div>
          <h1>Teams</h1>
          <div className="sub">Manage shared inboxes and team members.</div>
        </div>
        <button className="btn primary" onClick={() => setCreating(true)}>
          + Create Team
        </button>
      </div>

      {error && <div className="error-banner">{error}</div>}

      {creating ? (
        <div className="card" style={{ marginBottom: 16 }}>
          <h3>Create New Team</h3>
          <input
            type="text"
            value={newTeamName}
            onChange={(e) => setNewTeamName(e.target.value)}
            placeholder="Team name"
            style={{ width: "100%", marginTop: 8, marginBottom: 12 }}
          />
          <div style={{ display: "flex", gap: 8 }}>
            <button className="btn primary" onClick={createTeam} disabled={!newTeamName.trim()}>
              Create
            </button>
            <button className="btn" onClick={() => setCreating(false)}>
              Cancel
            </button>
          </div>
        </div>
      ) : (
        <button className="btn" onClick={() => setCreating(true)} style={{ marginBottom: 16 }}>
          + Create Team
        </button>
      )}

      <div className="team-list">
        {teams.length === 0 ? (
          <div className="empty">
            <h2>No teams yet</h2>
            <p>Create a team to share an inbox with colleagues.</p>
          </div>
        ) : (
          teams.map((team) => (
            <div
              key={team.id}
              className={`team-card ${selectedTeam?.id === team.id ? "selected" : ""}`}
              onClick={() => selectTeam(team)}
            >
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <div>
                  <div className="team-name">{team.name}</div>
                  <div className="team-meta">
                    {team.is_owner ? "Owner" : "Member"} ·{" "}
                    {team.members ? `${team.members.length} members` : ""}
                  </div>
                </div>
              </div>
            </div>
          ))
        )}
      </div>

      {selectedTeam && (
        <div className="card" style={{ marginTop: 24 }}>
          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 16 }}>
            <h2>{selectedTeam.name}</h2>
            <button className="btn" onClick={() => setSelectedTeam(null)}>
              Close
            </button>
          </div>

          <h3 style={{ marginBottom: 12 }}>Members</h3>
          {!selectedTeam.members || selectedTeam.members.length === 0 ? (
            <p className="muted">No members yet</p>
          ) : (
            <div className="member-list">
              {selectedTeam.members!.map((member) => (
                <div key={member.id} className="member-row">
                  <div>
                    <div className="member-name">{member.name}</div>
                    <div className="member-email">{member.email}</div>
                  </div>
                  <select
                    value={member.role}
                    onChange={(e) => updateRole(member, e.target.value as "admin" | "agent")}
                    className="role-select"
                  >
                    <option value="agent">Agent</option>
                    <option value="admin">Admin</option>
                  </select>
                  {member.user_id !== activeId && (
                    <button className="btn danger" onClick={(e) => { e.stopPropagation(); removeMember(member); }}>
                      Remove
                    </button>
                  )}
                </div>
              ))}
            </div>
          )}

          <div style={{ marginTop: 20, paddingTop: 16, borderTop: "1px solid var(--border)" }}>
            <h3>Invite Member</h3>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 8 }}>
              <select
                value={inviteEmail}
                onChange={(e) => setInviteEmail(e.target.value)}
                className="role-select"
                style={{ flex: 1, minWidth: 200 }}
              >
                <option value="">Select user…</option>
                {users
                  .filter((u) => u.id !== activeId && !selectedTeam.members?.some((m) => m.user_id === u.id))
                  .map((u) => (
                    <option key={u.id} value={u.email}>
                      {u.name} ({u.email})
                    </option>
                  ))}
              </select>
              <select
                value={inviteRole}
                onChange={(e) => setInviteRole(e.target.value as "admin" | "agent")}
                className="role-select"
                style={{ width: 140 }}
              >
                <option value="agent">Agent</option>
                <option value="admin">Admin</option>
              </select>
              <button className="btn primary" onClick={inviteMember} disabled={!inviteEmail}>
                Invite
              </button>
            </div>
          </div>
        </div>
      )}

      <style jsx>{`
        .team-list {
          display: flex;
          flex-direction: column;
          gap: 8px;
        }
        .team-card {
          border: 1px solid var(--border);
          border-radius: 8px;
          padding: 16px;
          cursor: pointer;
          transition: border-color 0.2s, background 0.2s;
        }
        .team-card:hover {
          border-color: var(--primary);
          background: var(--primary-weak);
        }
        .team-card.selected {
          border-color: var(--primary);
          background: var(--primary-weak);
        }
        .team-name {
          font-weight: 600;
          font-size: 16px;
        }
        .team-meta {
          font-size: 13px;
          color: var(--muted);
          margin-top: 4px;
        }
        .member-list {
          display: flex;
          flex-direction: column;
          gap: 8px;
        }
        .member-row {
          display: flex;
          align-items: center;
          gap: 12px;
          padding: 12px;
          border: 1px solid var(--border);
          border-radius: 8px;
        }
        .member-name {
          font-weight: 500;
        }
        .member-email {
          font-size: 13px;
          color: var(--muted);
        }
        .role-select {
          padding: 6px 10px;
          border: 1px solid var(--border);
          border-radius: 6px;
          background: var(--bg);
          color: var(--fg);
        }
      `}</style>
    </div>
  );
}