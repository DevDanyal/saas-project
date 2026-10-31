# API Reference

Base URL: `http://localhost:8000` (development) / `https://api.yourdomain.com` (production)

## Authentication

Currently uses user ID in path parameters. Future: JWT Bearer tokens.

## Rate Limits

| Endpoint Category | Limit |
|-------------------|-------|
| Auth | 10/minute |
| Billing | 30/minute (read), 10/minute (write) |
| Email Sync | 10/hour |
| Email Processing | 60/minute (single), 5/hour (batch) |
| Email Read | 60/minute |
| Draft Send | 30/minute |
| Webhooks | 100/minute |

Exceeding limits returns `429 Too Many Requests` with `Retry-After` header.

## Endpoints

---

### Authentication

#### Get Google OAuth URL
```
GET /auth/google
```

**Response:**
```json
{
  "authorization_url": "https://accounts.google.com/o/oauth2/auth?...",
  "state": "random-state-string"
}
```

#### OAuth Callback
```
GET /auth/google/redirect?code=...&state=...
```
Redirects to frontend with `connected=1&user_id=...&email=...`

---

### Email Management

#### Sync Gmail Inbox
```
POST /emails/sync/{user_id}
```

**Response:**
```json
{
  "threads": 50,
  "emails_added": 120,
  "emails_skipped": 5,
  "errors": 0
}
```

#### Process Single Email
```
POST /emails/process/{email_id}
```

**Response:**
```json
{
  "email_id": "uuid",
  "reader": {...},
  "category": "lead",
  "sentiment": {"mood": "positive", "intensity": 0.8, "warning": false},
  "priority": {"score": 92, "urgency": "high", "flags": ["hot_lead"]},
  "reply": {"reply_text": "...", "suggested_tone": "friendly"},
  "auto_decision": {"send": false, "confidence": 0.95, "reason": "..."},
  "drafts_created": 1,
  "actions_created": 2
}
```

#### Batch Process Inbox
```
POST /emails/process-all/{user_id}
```

**Response:**
```json
{
  "processed": 45,
  "errors": 0,
  "pending": 0
}
```

#### Send Draft Reply
```
POST /emails/drafts/{draft_id}/send
Content-Type: application/json

{"text": "Optional edited reply text"}
```

**Response:**
```json
{
  "draft_id": "uuid",
  "status": "sent",
  "sent_message_id": "gmail-message-id",
  "to": "sender@example.com",
  "subject": "Re: Original Subject"
}
```

#### List Inbox Threads
```
GET /emails/inbox/{user_id}?limit=100
```

**Response:**
```json
{
  "threads": [
    {
      "id": "uuid",
      "subject": "Lakefront buyer",
      "category": "lead",
      "priority_score": 92,
      "flags": ["hot_lead", "pre_approved"],
      "pipeline_hints": ["Hot lead", "Buyer pre-approved"],
      "summary": "Pre-approved buyer wants lakefront homes.",
      "last_activity_at": "2026-09-20T10:30:00Z",
      "emails": 3
    }
  ]
}
```

#### Get Thread Detail
```
GET /emails/threads/{thread_id}
```

**Response:**
```json
{
  "id": "uuid",
  "subject": "Lakefront buyer",
  "category": "lead",
  "priority_score": 92,
  "flags": ["hot_lead"],
  "pipeline_hints": ["Hot lead"],
  "summary": "Pre-approved buyer...",
  "last_activity_at": "2026-09-20T10:30:00Z",
  "emails": 3,
  "emails": [
    {
      "id": "uuid",
      "from_addr": "buyer@example.com",
      "to_addr": "agent@example.com",
      "subject": "Lakefront buyer",
      "received_at": "2026-09-20T10:30:00Z",
      "body": "Full email body...",
      "ai_summary": "Pre-approved buyer...",
      "sentiment": {"mood": "positive", "intensity": 0.8, "warning": false},
      "has_attachment": false,
      "draft": {
        "id": "uuid",
        "text": "AI draft reply...",
        "tone": "friendly",
        "status": "draft",
        "auto_decision": {"send": false, "confidence": 0.95, "reason": "..."},
        "sent_at": null
      },
      "actions": [
        {
          "id": "uuid",
          "type": "call",
          "description": "Call re: showings",
          "due": "2026-09-22T00:00:00Z",
          "contact": "buyer@example.com",
          "property": "lakefront",
          "status": "open"
        }
      ]
    }
  ]
}
```

#### Daily Digest
```
GET /emails/digest/{user_id}?hours=24
```

**Response:**
```json
{
  "generated_at": "2026-09-21T06:00:00Z",
  "window_hours": 24,
  "threads_in_window": 12,
  "actions_in_window": 8,
  "brief": "Three hot leads and one closing deadline needs attention today.",
  "sections": {
    "hot_leads": ["Smith wants lakefront", "Jones pre-approved"],
    "closings": ["123 Main St closing Friday"],
    "follow_ups": ["Call Brown re: offer"],
    "other": []
  }
}
```

#### Action Items
```
GET /emails/action-items/{user_id}
```

**Response:**
```json
{
  "action_items": [
    {
      "id": "uuid",
      "type": "call",
      "description": "Call re: showings",
      "due": "2026-09-22T00:00:00Z",
      "contact": "buyer@example.com",
      "property": "lakefront",
      "status": "open"
    }
  ]
}
```

---

### Notifications

#### List Notifications
```
GET /notifications/{user_id}?unread_only=false&limit=50
```

**Response:**
```json
{
  "notifications": [
    {
      "id": "uuid",
      "type": "hot_lead",
      "title": "Hot lead: Lakefront buyer",
      "body": "Pre-approved buyer wants...",
      "is_read": false,
      "thread_id": "uuid",
      "email_id": "uuid",
      "created_at": "2026-09-20T10:30:00Z"
    }
  ],
  "unread_count": 3
}
```

#### Mark Notification Read
```
POST /notifications/{notification_id}/read
```

**Response:**
```json
{
  "id": "uuid",
  "is_read": true
}
```

---

### Preferences

#### Get Preferences
```
GET /preferences/{user_id}
```

**Response:**
```json
{
  "tone_profile": {"style": "friendly", "formality": "medium"},
  "auto_features": {"autopilot": false, "autopilot_confidence": 0.9},
  "rules": "Never auto-reply to legal emails"
}
```

#### Update Preferences
```
PUT /preferences/{user_id}
Content-Type: application/json

{
  "autopilot": true,
  "autopilot_confidence": 0.95,
  "tone_profile": {"style": "professional"},
  "rules": "Custom rules..."
}
```

---

### Billing

#### Get Prices
```
GET /billing/prices
```

**Response:**
```json
{
  "free": {"price_id": "price_free", "name": "Free", "monthly_price": 0},
  "pro": {"price_id": "price_pro", "name": "Pro", "monthly_price": 29},
  "team": {"price_id": "price_team", "name": "Team", "monthly_price": 39}
}
```

#### Get Subscription
```
GET /billing/subscription/{user_id}
```

**Response:**
```json
{
  "plan": "pro",
  "status": "active",
  "current_period_end": "2026-10-27T00:00:00Z",
  "limits": {
    "emails_per_month": 5000,
    "smart_replies": -1,
    "autopilot": true,
    "calendar_sync": true
  }
}
```

#### Get Usage Limits
```
GET /billing/limits/{user_id}
```

**Response:**
```json
{
  "plan": "pro",
  "limits": {"emails_per_month": 5000, "smart_replies": -1, "autopilot": true, "calendar_sync": true},
  "usage": {"limit": 5000, "used": 1234, "remaining": 3766},
  "can_process": true
}
```

#### Create Checkout Session
```
POST /billing/checkout/{user_id}
Content-Type: application/json

{"price_id": "price_pro", "mode": "subscription"}
```

**Response:**
```json
{"url": "https://checkout.stripe.com/pay/..."}
```

#### Create Billing Portal Session
```
POST /billing/portal/{user_id}
```

**Response:**
```json
{"url": "https://billing.stripe.com/session/..."}
```

#### Stripe Webhook
```
POST /billing/webhook
Stripe-Signature: sig_...
```

---

### Teams

#### List Teams
```
GET /teams
```

**Response:**
```json
{
  "teams": [
    {
      "id": "uuid",
      "name": "Smith Realty",
      "owner_id": "uuid",
      "is_owner": true,
      "members": [...]
    }
  ]
}
```

#### Create Team
```
POST /teams
Content-Type: application/json

{"name": "My Team"}
```

**Response:**
```json
{"id": "uuid", "name": "My Team", "owner_id": "uuid"}
```

#### Get Team Detail
```
GET /teams/{team_id}
```

#### Add Team Member
```
POST /teams/{team_id}/members
Content-Type: application/json

{"user_id": "uuid", "role": "agent"}
```

#### Remove Team Member
```
DELETE /teams/{team_id}/members/{user_id}
```

#### Update Member Role
```
PATCH /teams/{team_id}/members/{user_id}
Content-Type: application/json

{"role": "admin"}
```

---

### Reports

#### Team Report
```
GET /reports/team/{team_id}?days=30
```

**Response:**
```json
{
  "team_id": "uuid",
  "team_name": "Smith Realty",
  "period_days": 30,
  "generated_at": "2026-09-27T06:00:00Z",
  "members_count": 3,
  "emails_processed": {
    "total": 1250,
    "by_member": {"agent1@example.com": 500, "agent2@example.com": 450, "agent3@example.com": 300}
  },
  "actions_created": {
    "total": 320,
    "by_member": {"agent1@example.com": 120, "agent2@example.com": 110, "agent3@example.com": 90}
  },
  "categories": {"lead": 400, "client": 350, "vendor": 200, "legal": 100, "financial": 80, "internal": 50, "spam": 50, "newsletter": 20},
  "priority_distribution": {"high": 150, "medium": 600, "low": 500},
  "notifications": {"hot_lead": 25, "urgent": 10, "closing": 15, "complaint": 5}
}
```

---

### Unsubscribe & Bounces

#### Unsubscribe Page (GET)
```
GET /unsubscribe?email=...&user_id=...&token=...
```
Returns HTML confirmation page.

#### Process Unsubscribe (POST)
```
POST /unsubscribe
Content-Type: application/x-www-form-urlencoded

email=...&user_id=...&token=...
```

#### Handle Bounce
```
POST /unsubscribe/bounce
Content-Type: application/json

{
  "email": "user@example.com",
  "type": "hard|soft|spam",
  "reason": "Mailbox full"
}
```

---

### Health Checks

```
GET /health
GET /health/live
GET /health/ready
```

**Response:**
```json
{"status": "ok"}
```

---

## Error Responses

All errors follow this format:

```json
{
  "detail": "Human-readable error message",
  // Or for validation errors:
  "detail": [
    {"loc": ["body", "field"], "msg": "Error message", "type": "value_error"}
  ]
}
```

Common HTTP status codes:
- `200` - Success
- `201` - Created
- `400` - Bad Request
- `401` - Unauthorized
- `403` - Forbidden (rate limit, plan limit)
- `404` - Not Found
- `422` - Validation Error
- `429` - Too Many Requests
- `500` - Internal Server Error
- `502` - Bad Gateway (external API failure)

---

## Webhooks

### Stripe Events Handled
- `checkout.session.completed` - Subscription created
- `customer.subscription.updated` - Plan changed
- `customer.subscription.deleted` - Cancelled
- `invoice.payment_failed` - Payment failed

### Gmail Push Notifications (Future)
- `message.new` - New email received
- `message.trashed` - Email deleted

---

## SDKs / Client Libraries

### JavaScript/TypeScript
```typescript
// Example API client
const API_URL = process.env.NEXT_PUBLIC_API_URL;

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...options?.headers },
    cache: 'no-store',
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export const api = {
  syncInbox: (userId: string) => request(`/emails/sync/${userId}`, { method: 'POST' }),
  processAll: (userId: string) => request(`/emails/process-all/${userId}`, { method: 'POST' }),
  getInbox: (userId: string) => request(`/emails/inbox/${userId}`),
  getThread: (threadId: string) => request(`/emails/threads/${threadId}`),
  sendDraft: (draftId: string, text?: string) => request(`/emails/drafts/${draftId}/send`, {
    method: 'POST',
    body: JSON.stringify({ text }),
  }),
  getDigest: (userId: string) => request(`/emails/digest/${userId}`),
  getActions: (userId: string) => request(`/emails/action-items/${userId}`),
  getSubscription: (userId: string) => request(`/billing/subscription/${userId}`),
  createCheckout: (userId: string, priceId: string) => request(`/billing/checkout/${userId}`, {
    method: 'POST',
    body: JSON.stringify({ price_id: priceId }),
  }),
};
```

---

## Changelog

### v0.1.0 (Current)
- Initial API with all core endpoints
- Rate limiting, security headers
- Stripe billing integration
- Team management
- Unsubscribe/bounce handling