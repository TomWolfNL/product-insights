import { cn } from "@/lib/utils";

export function ScoreBadge({ score, size = "md" }: { score: number; size?: "sm" | "md" | "lg" }) {
  const getScoreColor = (s: number) => {
    if (s >= 8) return "bg-score-high text-accent-foreground";
    if (s >= 6) return "bg-score-mid text-foreground";
    return "bg-score-low text-accent-foreground";
  };

  const sizeClasses = {
    sm: "text-xs px-1.5 py-0.5 min-w-[28px]",
    md: "text-sm px-2 py-1 min-w-[36px]",
    lg: "text-lg px-3 py-1.5 min-w-[44px] font-bold",
  };

  return (
    <span
      className={cn(
        "inline-flex items-center justify-center rounded-md font-semibold tabular-nums",
        getScoreColor(score),
        sizeClasses[size]
      )}
    >
      {score.toFixed(1)}
    </span>
  );
}
