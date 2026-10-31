# CLAUDE.md — Project Spec: Full Inbox AI Assistant for Real Estate Agents

> **Project status:** PLANNING (spec locked, implementation NOT started).
> Do not start building until the user says **"go for plan and implement"**.

---

## 1. Product Overview

A full inbox AI assistant SaaS for real estate agents. It connects to the agent's
email inbox, reads every conversation, and turns it into a clean, prioritized,
action-ready workspace.

**Tagline (working):** *Turn 100 emails into 1 page.*

### Core value prop
- Agent receives 100+ emails/day → the assistant saves 30+ min/day.
- Hot leads never get missed (priority scoring + notifications).
- No more lost action items — every task is extracted automatically.

---

## 2. Target User / Niche

- **Primary niche:** Real estate agents (buyer's and seller's agents).
- Future expansion: lawyers, finance advisors, insurance brokers.
- Testers in first phase: the developer's own real estate agent contacts.

---

## 3. Feature Set

### Core (MVP — Phase 3)
1. **Smart Inbox** — every email gets an AI mind: summary, priority, category, suggested reply.
2. **Auto-Categorization** — Lead / Client / Vendor / Legal / Financial / Internal / Spam / Newsletter.
3. **Priority Scoring** — urgency score 0-100, flags: hot lead, closing deadline, complaint, follow-up.
4. **1-Click Smart Replies** — AI drafts in the agent's tone; agent edits & sends.
5. **Daily Digest** — morning brief: hot leads, closings, overdue follow-ups.
6. **Action Items** — auto-extracted tasks (call/todo/event) viewable in dashboard.

### Extended (Phase 4)
7. **Auto-Pilot Mode** — auto-replies to low-risk, trusted emails (confidence cutoff).
8. **Calendar Sync** — action items become real Google Calendar events.
9. **Lead Pipeline Hints** — flags buyer/seller signals ("pre-approved", "ready to list").
10. **Notification Alerts** — push when a hot lead / urgent flag fires.
11. **Sentiment Flags** — mood detection on threads (angry/anxious client warnings).

### Team & Platform (Phase 5+)
12. Team/office accounts, shared inbox, roles (admin / agent).
13. CRM field sync (HubSpot-style), lead stage updates.
14. Mobile app (React Native).
15. Public API for integrations.

---

## 4. Architecture — The AI Brain

### Orchestrator (Main Agent: "Inbox Director")
Every arriving email → orchestrator runs the pipeline and delegates to sub-agents.

### Sub-agents (Python + LLM, prompt + strict JSON output)

| # | Agent | Input | Output |
|---|-------|-------|--------|
| 1 | **Reader** | raw email (headers/body/attachments text) | `{from, to, subject, received_at, body_clean, thread_id, has_attachment, reply_depth}` |
| 2 | **Categorizer** | cleaned email | `{category}` (see categories) |
| 3 | **Sentiment** | cleaned email | `{mood, intensity, warning}` |
| 4 | **Prioritizer** | category + email | `{score 0-100, urgency, flags[]}` |
| 5 | **Reply Drafter** | thread + tone profile | `{reply_text, suggested_tone}` |
| 6 | **Action Extractor** | email + thread | `{actions:[{type, description, due, contact, property}]}` |
| 7 | **Digest** (daily) | today's outputs | morning brief text |
| 8 | **Auto-Pilot** (Phase 4) | categories+sentiment+drafts | `{send, confidence, reason}` |

### Pipeline flow (per email)
```
Email arrives
  → Reader cleans it
  → Categorizer + Sentiment (parallel)
  → Prioritizer scores
  → Reply Drafter (only as needed)
  → Action Extractor
  → Persist + show in Smart Inbox
  → Nightly: Digest builds morning brief
```

**AI cost target:** ~$0.001–0.003 per email (3–5 small model calls).

### MCP Servers (the tools/hands)
| Server | Tools | Notes |
|--------|-------|-------|
| **Gmail MCP** | list_threads, read_email, send_reply, mark_as, search | Phase 3 |
| **Calendar MCP** | create_event, propose_time_slot, check_availability | Phase 4 |
| **CRM MCP** | upsert_contact, update_lead_stage, log_activity | Phase 5 |
| **Knowledge MCP** | get_agent_preferences, get_tone_profile, get_response_templates, remember_decision | Phase 3 |
| **Lead-Intel MCP** | lookup_listing, price_history, market_alert | Phase 5+ |

### Skills (training + rulebooks)
**Product skills (loaded by agents):**
1. **Real-Estate Domain Skill** — vocabulary, contracts, inspection, closing timeline, MLS codes.
2. **Client Communication Skill** — lead response rules, tone guidelines.
3. **Error-Recovery Skill** — weird emails, forwarded threads, PDF offers, spam traps.
4. **Compliance & Legal Boundaries Skill** — what the AI must NEVER do (quote terms, promise financing, act as attorney). **Always loaded — safety guardrail.**
5. **Tone-Personalization Skill** — per-agent voice profiles.
6. **Digest-Formatting Skill** — morning-brief layout rules.

**Dev-time skills (created and used while building):**
1. Email-Integration Skill — Gmail/Outlook OAuth setup guide.
2. Agent-Build Skill — sub-agent template (prompt + JSON schema + tests).
3. Agent-Test Skill — realistic real-estate test-email bank.
4. MCP-Build Skill — MCP server template.
5. Frontend-UI Skill — Smart Inbox dashboard patterns.
6. Deploy-Skill — production rollout checklist.

---

## 5. Tech Stack

| Layer | Choice | Notes |
|-------|--------|-------|
| Backend | Python + FastAPI | Business logic + agent orchestration |
| Email | Gmail API (+ Microsoft Graph later) | OAuth 2.0 |
| AI | OpenAI / Claude API | LLM + agent function calls |
| Frontend | React / Next.js | Smart Inbox dashboard |
| Database | PostgreSQL | Neon / Supabase free tier for dev |
| Auth | Google OAuth + session auth | (Supabase Auth candidate) |
| Payments | Stripe | subscriptions, plans |
| Hosting | localhost dev → Vercel + small server | production later |

---

## 6. Data Model (Phase 1 of build)

- **users** — id, name, email, oauth_tokens (encrypted), role
- **email_accounts** — id, user_id, provider, scope, connected_at, token_cache
- **threads** — id, user_id, subject, thread_id, last_sync_at, category, priority
- **emails** — id, thread_id, from, to, body, received_at, ai_summary, sentiment
- **ai_drafts** — id, email_id, text, tone, status (draft/edited/sent/rejected)
- **action_items** — id, email_id, type, description, due, contact, property, status
- **agent_preferences** — id, user_id, tone_profile, auto_features, rules
- **subscriptions** — id, user_id, plan, stripe_customer_id, status

---

## 7. Security & Privacy (non-negotiable)

- **Limited OAuth scopes** — start read-only (`gmail.readonly`); write scope only when reply send is enabled and user approves.
- **Encryption** — email content and tokens encrypted at rest.
- **Data retention** — never keep raw email longer than needed; purge on account disconnect.
- **AI guardrails** — Compliance skill always loaded; drafts always editable; no silent sends without consent.
- **User transparency** — clear consent prompts during onboarding ("We can read and summarize your email").

---

## 8. Onboarding Flow

1. Sign up (Google OAuth).
2. Connect Gmail (approve scopes).
3. Train the AI (2-5 min): agent picks tone, example reply style, rules.
4. Background sync of recent threads.
5. First Smart Inbox + daily digest.

---

## 9. Pricing (initial plan)

- **Free tier:** 200 emails/mo (AI processing), smart replies limited, digest yes.
- **Pro tier (~$29-49/mo):** 5,000 emails/mo, full smart replies, auto-pilot, calendar sync.
- **Team tier (per seat, ~$39/mo):** shared inbox, shared digest, roles, team reports.
- Add-ons: extra AI credits, extended store of action items.

---

## 10. Build Roadmap (relaxed pace — step by step)

### Phase 0 — Foundations
- Repo init, project structure, dev environment (Python venv + Node), tooling.

### Phase 1 — Data Layer
- PostgreSQL schema, migrations, models, DB helpers.

### Phase 2 — Email Integration
- Gmail API project, OAuth flow, token storage, fetch + email ingestion.

### Phase 3 — AI Engine + Core MVP
- LLM client wrapper, Reader/Categorizer/Sentiment/Prioritizer/Reply Drafter/
  Action Extractor agents, Knowledge MCP, Smart Inbox frontend, Digest.

### Phase 4 — Extended Features
- Auto-Pilot, Calendar MCP, notifications, sentiment flags polish.

### Phase 5 — Billing & Team
- Stripe subscriptions, plan limits, team accounts, CRM MCP.

### Phase 6 — Polish & Launch
- Security review, email deliverability, testing, deployment, docs.

---

## 11. Working Agreement

- **Pace:** relaxed, step by step. We never skip or rush; each phase is verified before moving on.
- **Trigger to start building:** the user says **"go for plan and implement"**.
- **Money note (dev costs):** build + test is near-free (AI API = a few dollars total
  while testing). Paid costs start only at production (hosting ~$5-20/mo, Stripe ~2.9%).