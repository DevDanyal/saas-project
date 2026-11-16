"use client";

import { useEffect, useState } from "react";
import { UserPlus, Users } from "lucide-react";
import { del, get, patch, post } from "@/lib/api";
import type { Team, TeamMember } from "@/lib/types";
import { useUser } from "@/lib/user-context";

export default function TeamsPage() {
  const { activeId } = useUser();
  const [teams, setTeams] = useState<Team[]>([]);
  const [selectedTeam, setSelectedTeam] = useState<Team | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [newTeamName, setNewTeamName] = useState("");
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState<"admin" | "agent">("agent");

  useEffect(() => {
    if (!activeId) return;
    let cancelled = false;
    (async () => {
      try {
        const data = await get<{ teams: Team[] }>("/teams");
        if (!cancelled) setTeams(data.teams || []);
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [activeId]);

  async function createTeam() {
    if (!newTeamName.trim()) return;
    try {
      const team = await post<Team>("/teams", { name: newTeamName.trim() });
      setTeams((prev) => [...prev, team]);
      setNewTeamName("");
    } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
  }

  async function selectTeam(team: Team) {
    try { setSelectedTeam(await get<Team>(`/teams/${team.id}`)); }
    catch (e) { setError(e instanceof Error ? e.message : String(e)); }
  }

  async function inviteMember() {
    if (!selectedTeam || !inviteEmail.trim()) return;
    try {
      await post(`/teams/${selectedTeam.id}/members`, { email: inviteEmail.trim(), role: inviteRole });
      await selectTeam(selectedTeam);
      setInviteEmail("");
    } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
  }

  async function removeMember(member: TeamMember) {
    if (!selectedTeam || !confirm(`Remove ${member.name} from this team?`)) return;
    try { await del(`/teams/${selectedTeam.id}/members/${member.user_id}`); await selectTeam(selectedTeam); }
    catch (e) { setError(e instanceof Error ? e.message : String(e)); }
  }

  async function updateRole(member: TeamMember, role: "admin" | "agent") {
    if (!selectedTeam) return;
    try { await patch(`/teams/${selectedTeam.id}/members/${member.user_id}`, { role }); await selectTeam(selectedTeam); }
    catch (e) { setError(e instanceof Error ? e.message : String(e)); }
  }

  if (!activeId) return <div className="empty"><h2>No account</h2><p>Select an account to manage teams.</p></div>;
  if (loading) return <div className="card card-pad sub">Loading teams?</div>;

  return (
    <div className="stack">
      <div className="page-head">
        <div>
          <h1>Teams</h1>
          <div className="sub">Share inboxes, assign roles, and collaborate with your team.</div>
        </div>
      </div>

      {error && <div className="error-banner">{error}</div>}

      <div className="grid-3">
        <div className="card card-pad stack" style={{ gridColumn: "span 1" }}>
          <div className="label">Create team</div>
          <input className="input" type="text" value={newTeamName} onChange={(e) => setNewTeamName(e.target.value)} placeholder="Team name" />
          <button className="btn primary" onClick={() => void createTeam()} disabled={!newTeamName.trim()}><Users size={14} /> Create team</button>
          <div className="label" style={{ marginTop: 8 }}>Your teams</div>
          {teams.length === 0 ? (
            <div className="sub">No teams yet.</div>
          ) : (
            <div className="stack" style={{ gap: 8 }}>
              {teams.map((team) => (
                <button key={team.id} className={`card card-pad ${selectedTeam?.id === team.id ? "ai-brief" : ""}`} onClick={() => void selectTeam(team)} style={{ textAlign: "left", cursor: "pointer", width: "100%" }}>
                  <div style={{ fontWeight: 700, fontSize: 14, overflowWrap: "anywhere" }}>{team.name}</div>
                  <div className="sub">{team.is_owner ? "Owner" : "Member"}{team.members ? ` ? ${team.members.length} members` : ""}</div>
                </button>
              ))}
            </div>
          )}
        </div>

        <div className="card card-pad stack" style={{ gridColumn: "span 2", minHeight: 320 }}>
          {!selectedTeam ? (
            <div className="empty" style={{ margin: "auto 0" }}><h2>Select a team</h2><p>Choose a team to view members and send invites.</p></div>
          ) : (
            <>
              <div className="row" style={{ justifyContent: "space-between" }}>
                <div style={{ minWidth: 0 }}>
                  <div style={{ fontSize: 18, fontWeight: 700, overflowWrap: "anywhere" }}>{selectedTeam.name}</div>
                  <div className="sub">{selectedTeam.members?.length ?? 0} members</div>
                </div>
                <button className="btn sm ghost" onClick={() => setSelectedTeam(null)}>Close</button>
              </div>

              <div>
                <div className="label">Members</div>
                {!selectedTeam.members || selectedTeam.members.length === 0 ? (
                  <div className="sub">No members yet.</div>
                ) : (
                  <div className="stack" style={{ gap: 8 }}>
                    {selectedTeam.members.map((member) => (
                      <div key={member.id} className="card card-pad" style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
                        <div style={{ minWidth: 0, flex: 1 }}>
                          <div style={{ fontWeight: 600, fontSize: 14, overflowWrap: "anywhere" }}>{member.name}</div>
                          <div className="sub" style={{ overflowWrap: "anywhere" }}>{member.email}</div>
                        </div>
                        <div className="row" style={{ gap: 8 }}>
                          <select className="select" value={member.role} onChange={(e) => void updateRole(member, e.target.value as "admin" | "agent")} style={{ width: 130 }}>
                            <option value="agent">Agent</option>
                            <option value="admin">Admin</option>
                          </select>
                          {member.user_id !== activeId && <button className="btn sm danger" onClick={() => void removeMember(member)}>Remove</button>}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              <div className="card card-pad" style={{ background: "var(--surface-muted)" }}>
                <div className="label">Invite member</div>
                <div className="row" style={{ alignItems: "stretch" }}>
                  <input className="input" type="email" value={inviteEmail} onChange={(e) => setInviteEmail(e.target.value)} placeholder="agent@example.com" style={{ flex: 1, minWidth: 160 }} />
                  <select className="select" value={inviteRole} onChange={(e) => setInviteRole(e.target.value as "admin" | "agent")} style={{ width: 130 }}>
                    <option value="agent">Agent</option>
                    <option value="admin">Admin</option>
                  </select>
                  <button className="btn primary" onClick={() => void inviteMember()} disabled={!inviteEmail.trim()}><UserPlus size={14} /> Invite</button>
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
