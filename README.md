# Full Inbox AI Assistant for Real Estate Agents

Turn 100 emails into 1 page.

A full inbox AI assistant SaaS that connects to a real estate agent's email,
reads every conversation, and turns it into a clean, prioritized, action-ready
workspace: summaries, categories, priority scores, 1-click smart replies, action
items, and a daily digest.

Project spec and roadmap: see **CLAUDE.md**.

## Repo layout

```
backend/    Python + FastAPI (agent orchestration, email integration, MCP servers)
frontend/   React / Next.js (Smart Inbox dashboard)
docs/       Build notes and planning docs
```

## Features

### Core (MVP - Phase 3)
- **Smart Inbox** - Every email gets an AI mind: summary, priority, category, suggested reply
- **Auto-Categorization** - Lead / Client / Vendor / Legal / Financial / Internal / Spam / Newsletter
- **Priority Scoring** - Urgency score 0-100, flags: hot lead, closing deadline, complaint, follow-up
- **1-Click Smart Replies** - AI drafts in the agent's tone; agent edits & sends
- **Daily Digest** - Morning brief: hot leads, closings, overdue follow-ups
- **Action Items** - Auto-extracted tasks (call/todo/event) viewable in dashboard

### Extended (Phase 4)
- **Auto-Pilot Mode** - Auto-replies to low-risk, trusted emails (confidence cutoff)
- **Calendar Sync** - Action items become real Google Calendar events
- **Lead Pipeline Hints** - Flags buyer/seller signals ("pre-approved", "ready to list")
- **Notification Alerts** - Push when a hot lead / urgent flag fires
- **Sentiment Flags** - Mood detection on threads (angry/anxious client warnings)

### Billing & Team (Phase 5)
- **Stripe Subscriptions** - Free (200 emails/mo), Pro ($29/mo, 5000 emails), Team ($39/seat)
- **Team Accounts** - Shared inbox, roles (admin/agent), team reports
- **Plan Limits Enforcement** - Automatic limit checking on AI processing

### Security (Phase 6)
- Rate limiting on all API endpoints
- Security headers (CSP, X-Frame-Options, etc.)
- CORS configuration
- Unsubscribe handling with secure tokens
- Bounce processing (hard/soft/spam)
- Encrypted token storage

## Quick Start

### Prerequisites
- Python 3.12+
- Node.js 20+
- PostgreSQL 16+
- Google Cloud project with Gmail API enabled
- Stripe account (for billing)

### Local Development

1. **Clone and configure**
   ```bash
   git clone <repo>
   cd saas-landingpage
   cp .env.example .env
   # Edit .env with your credentials
   ```

2. **Start database**
   ```bash
   docker-compose up -d postgres
   ```

3. **Backend setup**
   ```bash
   cd backend
   pip install -r requirements.txt
   python -m alembic upgrade head
   uvicorn app.main:app --reload
   ```

4. **Frontend setup**
   ```bash
   cd frontend
   npm install
   npm run dev
   ```

5. **Access**
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:8000
   - API Docs: http://localhost:8000/docs

### Docker (Production-like)

```bash
docker-compose up -d
```

## Environment Variables

See `.env.example` for all required variables.

| Variable | Description | Required |
|----------|-------------|----------|
| `DATABASE_URL` | PostgreSQL connection string | Yes |
| `ENCRYPTION_KEY` | 32-byte key for token encryption | Yes |
| `GOOGLE_CLIENT_ID` | Google OAuth client ID | Yes |
| `GOOGLE_CLIENT_SECRET` | Google OAuth client secret | Yes |
| `GOOGLE_REDIRECT_URI` | OAuth redirect URI | Yes |
| `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` / `GEMINI_API_KEY` | At least one AI provider | Yes |
| `FRONTEND_URL` | Frontend URL for CORS | Yes |
| `STRIPE_SECRET_KEY` | Stripe secret key | For billing |
| `STRIPE_WEBHOOK_SECRET` | Stripe webhook secret | For billing |

## API Documentation

- **OpenAPI/Swagger**: `GET /docs` (development only)
- **ReDoc**: `GET /redoc` (development only)

### Key Endpoints

| Endpoint | Description |
|----------|-------------|
| `POST /auth/google` | Get Google OAuth URL |
| `GET /auth/google/redirect` | OAuth callback |
| `POST /emails/sync/{user_id}` | Sync Gmail inbox |
| `POST /emails/process-all/{user_id}` | Run AI on unprocessed emails |
| `GET /emails/inbox/{user_id}` | List threads with AI summaries |
| `GET /emails/threads/{thread_id}` | Full thread detail |
| `POST /emails/drafts/{draft_id}/send` | Send AI draft reply |
| `GET /emails/digest/{user_id}` | Daily morning brief |
| `GET /emails/action-items/{user_id}` | All action items |
| `GET /billing/subscription/{user_id}` | Current plan & limits |
| `POST /billing/checkout/{user_id}` | Create Stripe checkout |
| `GET /teams` | List user's teams |
| `POST /teams` | Create team |
| `GET /reports/team/{team_id}` | Team activity report |
| `GET /unsubscribe` | Unsubscribe page |
| `POST /unsubscribe/bounce` | Handle email bounces |

## Database Schema

See `backend/app/db/models.py` for complete models:
- `User` - Agent accounts
- `EmailAccount` - Connected Gmail/Outlook accounts
- `Thread` - Email threads with AI analysis
- `Email` - Individual emails
- `AiDraft` - AI-generated reply drafts
- `ActionItem` - Extracted tasks
- `Subscription` - Stripe subscription status
- `Team` / `TeamMember` - Team accounts
- `Notification` - Alert notifications

## Testing

```bash
# Backend tests
cd backend
python -m pytest tests/ -v

# Frontend tests
cd frontend
npm run typecheck
npm run lint
npm run build
```

## Deployment

### Docker Compose (Single Server)

```bash
# Configure .env with production values
docker-compose -f docker-compose.yml up -d
```

### Kubernetes

1. Build and push images:
   ```bash
   docker build -t your-registry/inbox-backend ./backend
   docker build -t your-registry/inbox-frontend ./frontend
   docker push your-registry/inbox-backend
   docker push your-registry/inbox-frontend
   ```

2. Apply manifests (create `k8s/` directory with Deployments, Services, Ingress)

### Health Checks

- Backend: `GET /health`, `GET /health/live`, `GET /health/ready`
- Frontend: `GET /` (returns 200 if built)

## Security Checklist

- [ ] Use strong `ENCRYPTION_KEY` (32 random bytes)
- [ ] Rotate `SESSION_SECRET` periodically
- [ ] Use HTTPS in production (`GOOGLE_REDIRECT_URI`, `FRONTEND_URL`)
- [ ] Configure Stripe webhook endpoint with secret
- [ ] Set up SPF/DKIM/DMARC for sending domain
- [ ] Monitor rate limit logs
- [ ] Review CSP headers for your domain

## Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Frontend  │────▶│   Backend   │────▶│  PostgreSQL │
│  (Next.js)  │     │  (FastAPI)  │     │             │
└─────────────┘     └──────┬──────┘     └─────────────┘
                           │
                    ┌──────┴──────┐
                    │  Gmail API  │
                    │  Stripe API │
                    │  AI APIs    │
                    └─────────────┘
```

## License

Proprietary - All rights reserved.