export function scoreClass(score: number | null): string {
  if (score == null) return "na";
  if (score >= 85) return "hot";
  if (score >= 60) return "warm";
  return "ok";
}

export function CategoryChip({ category }: { category: string | null }) {
  if (!category) return <span className="chip plain">unknown</span>;
  if (category === "lead" || category === "client")
    return <span className="chip hot">{category}</span>;
  if (category === "legal" || category === "financial")
    return <span className="chip warm">{category}</span>;
  if (category === "spam") return <span className="chip plain">{category}</span>;
  return <span className="chip neutral">{category}</span>;
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