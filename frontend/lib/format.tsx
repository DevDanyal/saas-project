export function scoreClass(score: number | null): string {
  if (score == null) return "na";
  if (score >= 85) return "hot";
  if (score >= 60) return "warm";
  return "ok";
}

const CATEGORY_LABELS: Record<string, string> = {
  lead: "Lead",
  client: "Customer",
  vendor: "Vendor",
  legal: "Legal",
  financial: "Financial",
  internal: "Internal",
  spam: "Spam",
  newsletter: "Newsletter",
};

export function CategoryChip({ category }: { category: string | null }) {
  if (!category) return <span className="chip plain">unknown</span>;
  const label = CATEGORY_LABELS[category] ?? category;
  if (category === "lead" || category === "client")
    return <span className="chip hot">{label}</span>;
  if (category === "legal" || category === "financial")
    return <span className="chip warm">{label}</span>;
  if (category === "spam") return <span className="chip plain">{label}</span>;
  return <span className="chip neutral">{label}</span>;
}

export function ReplyStatusChip({ status }: { status?: string }) {
  if (!status || status === "none") return null;
  if (status === "replied") return <span className="chip ok">Replied</span>;
  if (status === "draft_ready")
    return <span className="chip primary">Reply ready</span>;
  if (status === "needs_reply")
    return <span className="chip warm">Needs reply</span>;
  return null;
}

export function FlagChip({ flag }: { flag: string }) {
  const clean = flag.replace(/_/g, " ");
  const cls = /hot|deadline|complaint|urgent/.test(flag) ? "hot" : "warm";
  return <span className={`chip ${cls}`}>{clean}</span>;
}

export function HintChip({ hint }: { hint: string }) {
  const cls = /pre-approved|ready to list|hot/i.test(hint) ? "hot" : "neutral";
  return <span className={`chip ${cls}`}>{hint}</span>;
}

export function MoodChip({
  sentiment,
}: {
  sentiment: { mood: string; intensity: number; warning: boolean } | null;
}) {
  if (!sentiment) return null;
  const cls =
    sentiment.warning || sentiment.mood === "negative" || sentiment.mood === "urgent"
      ? "hot"
      : sentiment.mood === "positive"
        ? "ok"
        : "neutral";
  return (
    <span className={`chip ${cls}`}>
      {sentiment.mood}
      {sentiment.warning ? " !" : ""}
    </span>
  );
}

export function formatTime(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function formatDate(iso: string | null): string {
  if (!iso) return "no date";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

export function cleanEmailBody(text: string | null | undefined): string {
  if (!text) return "";
  return text
    .replace(/\r\n?/g, "\n")
    .replace(/\(\s*https?:\/\/[^)\s]*\s*\)/gi, " ")
    .replace(/<\s*https?:\/\/[^>\s]*\s*>/gi, " ")
    .replace(/https?:\/\/\S+/gi, " ")
    .split("\n")
    .map((line) => line.replace(/[ \t\f\v]+/g, " ").trim())
    .filter((line) => line && !/^[\s,.;:!?|•·*#\-_=]+$/.test(line))
    .join("\n")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}