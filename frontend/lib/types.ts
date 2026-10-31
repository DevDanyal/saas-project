export type User = {
  id: string;
  name: string;
  email: string;
  role: string;
  created_at?: string | null;
  gmail_connected?: boolean;
};

export type ThreadFlags = string[];

export type ThreadSummary = {
  id: string;
  subject: string;
  category: string | null;
  priority_score: number | null;
  flags: ThreadFlags;
  pipeline_hints: string[];
  summary: string | null;
  last_activity_at: string | null;
  emails: number;
};

export type EmailSentiment = {
  mood: string;
  intensity: number;
  warning: boolean;
};

export type ActionItem = {
  id: string;
  type: string;
  description: string;
  due: string | null;
  contact: string | null;
  property: string | null;
  status: string;
};

export type AutoDecision = {
  send: boolean;
  confidence: number;
  reason: string;
  blockers: string[];
};

export type Draft = {
  id: string;
  text: string;
  tone: string;
  status?: string;
  auto_decision?: AutoDecision | null;
  sent_at?: string | null;
};

export type ThreadEmail = {
  id: string;
  from_addr: string;
  to_addr: string;
  subject: string;
  received_at: string | null;
  body: string;
  ai_summary: string | null;
  sentiment: EmailSentiment | null;
  has_attachment: boolean;
  draft: Draft | null;
  actions: ActionItem[];
};

export type ThreadDetail = ThreadSummary & {
  emails: ThreadEmail[];
};

export type DigestSections = {
  hot_leads: string[];
  closings: string[];
  follow_ups: string[];
  other: string[];
};

export type Digest = {
  generated_at: string;
  window_hours: number;
  threads_in_window: number;
  actions_in_window: number;
  brief: string;
  sections: DigestSections;
};

export type SyncStats = {
  threads: number;
  emails_added: number;
  emails_skipped: number;
  errors: number;
};

export type ProcessStats = {
  processed: number;
  errors: number;
  pending: number;
};

export type Notification = {
  id: string;
  type: string;
  title: string;
  body: string | null;
  is_read: boolean;
  thread_id: string | null;
  email_id: string | null;
  created_at: string | null;
};

export type NotificationList = {
  notifications: Notification[];
  unread_count: number;
};

export type Preferences = {
  tone_profile: Record<string, unknown>;
  auto_features: {
    autopilot?: boolean;
    autopilot_confidence?: number;
    [key: string]: unknown;
  };
  rules: string | null;
};

export type PlanLimits = {
  emails_per_month: number;
  smart_replies: number;
  autopilot: boolean;
  calendar_sync: boolean;
};

export type Subscription = {
  plan: "free" | "pro" | "team";
  status: string;
  current_period_end: string | null;
  limits: PlanLimits;
};

export type BillingUsage = {
  limit: number;
  used: number;
  remaining: number;
};

export type Price = {
  price_id: string;
  name: string;
  monthly_price: number;
};

export type TeamMember = {
  id: string;
  user_id: string;
  email: string;
  name: string;
  role: "admin" | "agent";
  joined_at: string | null;
};

export type Team = {
  id: string;
  name: string;
  owner_id: string;
  is_owner: boolean;
  members?: TeamMember[];
};

export type TeamReport = {
  team_id: string;
  team_name: string;
  period_days: number;
  generated_at: string;
  members_count: number;
  emails_processed: {
    total: number;
    by_member: Record<string, number>;
  };
  actions_created: {
    total: number;
    by_member: Record<string, number>;
  };
  categories: Record<string, number>;
  priority_distribution: {
    high: number;
    medium: number;
    low: number;
  };
  notifications: Record<string, number>;
};