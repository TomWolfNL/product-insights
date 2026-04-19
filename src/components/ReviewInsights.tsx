import { ThumbsUp, ThumbsDown, BarChart3, Store, ExternalLink } from "lucide-react";
import { cn } from "@/lib/utils";
import { useCountUp } from "@/hooks/useCountUp";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Area,
  AreaChart,
} from "recharts";

interface Insight {
  id: string;
  label: string;
  sentiment: string;
  mention_count: number;
}

interface Webshop {
  id: string;
  webshop_name: string;
  webshop_url: string | null;
  price_eur: number;
  review_count: number;
}

const STANDARD_CRITERIA = [
  "Performance",
  "Design",
  "Battery",
  "Camera",
  "Display",
  "Value for Money",
  "Software",
  "Audio",
  "Storage",
  "Connectivity",
  "Security",
  "Hardware",
];

const animationStyles = `
  @keyframes fillBar {
    from {
      width: 0%;
    }
    to {
      width: var(--bar-width);
    }
  }
  
  .animate-fill-criteria {
    animation: fillBar 1.2s ease-out forwards;
  }
`;

function CriteriaItem({ criterion, positive, negative, neutral, total }: { criterion: string; positive: number; negative: number; neutral: number; total: number }) {
  const posRatio = total > 0 ? positive / total : 0;
  const negRatio = total > 0 ? negative / total : 0;
  const neuRatio = total > 0 ? neutral / total : 0;
  
  const posPercentage = Math.round(posRatio * 100);
  const negPercentage = Math.round(negRatio * 100);
  
  const animatedPositive = useCountUp(posPercentage, 1200);
  const animatedNegative = useCountUp(negPercentage, 1200);
  
  if (total === 0) {
    return (
      <div>
        <div className="flex items-center justify-between mb-1">
          <span className="text-xs font-medium text-foreground">{criterion}</span>
          <span className="text-[10px] text-muted-foreground">—</span>
        </div>
        <div className="h-3 w-full rounded-full bg-muted" />
      </div>
    );
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <span className="text-xs font-medium text-foreground">{criterion}</span>
        <span className="text-[10px] text-muted-foreground">{total}</span>
      </div>
      <div className="flex h-3 w-full rounded-full overflow-hidden bg-muted">
        <div 
          className="bg-sentiment-negative animate-fill-criteria" 
          style={{ "--bar-width": `${negRatio * 100}%` } as React.CSSProperties} 
        />
        <div 
          className="bg-sentiment-neutral animate-fill-criteria" 
          style={{ "--bar-width": `${neuRatio * 100}%`, animationDelay: "0s" } as React.CSSProperties} 
        />
        <div 
          className="bg-sentiment-positive animate-fill-criteria" 
          style={{ "--bar-width": `${posRatio * 100}%`, animationDelay: "0s" } as React.CSSProperties} 
        />
      </div>
      <div className="flex justify-between mt-0.5">
        <span className="text-[10px] text-sentiment-negative">{animatedNegative}%</span>
        <span className="text-[10px] text-sentiment-neutral">{Math.round(neuRatio * 100)}%</span>
        <span className="text-[10px] text-sentiment-positive">{animatedPositive}%</span>
      </div>
    </div>
  );
}

interface TimelineEntry {
  year?: string;
  month?: string;
  sentiment: string;
  count: number;
}

interface ReviewInsightsProps {
  insights: Insight[];
  webshops?: Webshop[];
  timeline?: TimelineEntry[];
}

export function ReviewInsights({ insights, webshops, timeline }: ReviewInsightsProps) {
  if (!insights || insights.length === 0) return null;

  const totalMentions = insights.reduce((sum, i) => sum + i.mention_count, 0);
  const totalReviews = webshops?.reduce((sum, w) => sum + w.review_count, 0) ?? totalMentions;

  const totalPositive = insights.filter(i => i.sentiment === "positive").reduce((s, i) => s + i.mention_count, 0);
  const totalNegative = insights.filter(i => i.sentiment === "negative").reduce((s, i) => s + i.mention_count, 0);
  const totalNeutral = insights.filter(i => i.sentiment === "neutral").reduce((s, i) => s + i.mention_count, 0);
  const sentimentTotal = totalPositive + totalNegative + totalNeutral || 1;

  // Build monthly timeline from real data
  const reviewTimeline = (() => {
    if (timeline && timeline.length > 0) {
      const monthMap: Record<string, { positive: number; neutral: number; negative: number }> = {};
      timeline.forEach((t) => {
        const key = String(t.month || t.year || "");
        if (!key) return;
        if (!monthMap[key]) monthMap[key] = { positive: 0, neutral: 0, negative: 0 };
        if (t.sentiment === "positive") monthMap[key].positive += t.count;
        else if (t.sentiment === "negative") monthMap[key].negative += t.count;
        else monthMap[key].neutral += t.count;
      });
      return Object.entries(monthMap)
        .sort(([a], [b]) => a.localeCompare(b))
        .map(([period, counts]) => ({ period, ...counts }));
    }
    return [];
  })();

  // Map insights to criteria with positive/negative counts
  const criteriaData = STANDARD_CRITERIA.map((criterion) => {
    const matching = insights.filter(
      (i) =>
        i.label.toLowerCase().includes(criterion.toLowerCase()) ||
        criterion.toLowerCase().includes(i.label.toLowerCase().split(" ")[0])
    );
    const positive = matching
      .filter((m) => m.sentiment === "positive")
      .reduce((s, m) => s + m.mention_count, 0);
    const negative = matching
      .filter((m) => m.sentiment === "negative")
      .reduce((s, m) => s + m.mention_count, 0);
    const neutral = matching
      .filter((m) => m.sentiment === "neutral")
      .reduce((s, m) => s + m.mention_count, 0);
    const total = positive + negative + neutral;
    return { criterion, positive, negative, neutral, total };
  });

  const positiveInsights = insights
    .filter((i) => i.sentiment === "positive")
    .sort((a, b) => b.mention_count - a.mention_count);
  const negativeInsights = insights
    .filter((i) => i.sentiment === "negative")
    .sort((a, b) => b.mention_count - a.mention_count);

  return (
    <>
      <style>{animationStyles}</style>
      <div className="flex flex-col gap-6 mt-4">
        <h3 className="text-base font-bold font-display text-foreground flex items-center gap-2">
          <BarChart3 className="h-4 w-4 text-primary" />
          Review Insights
          <span className="text-xs font-normal text-muted-foreground ml-1">
            ({totalMentions.toLocaleString()} mentions)
          </span>
        </h3>

        {/* Reviews by year - area/line graph */}
        <div className="rounded-lg border border-border bg-card p-4">
          <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-3">
            Reviews Over Time
          </h4>
          <div className="h-40">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={reviewTimeline}>
                <defs>
                  <linearGradient id="posGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="hsl(var(--positive))" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="hsl(var(--positive))" stopOpacity={0} />
                  </linearGradient>
                  <linearGradient id="neuGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="hsl(var(--neutral))" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="hsl(var(--neutral))" stopOpacity={0} />
                  </linearGradient>
                  <linearGradient id="negGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="hsl(var(--negative))" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="hsl(var(--negative))" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <XAxis dataKey="period" tick={{ fontSize: 10 }} stroke="hsl(var(--muted-foreground))" axisLine={false} tickLine={false} interval="preserveStartEnd" angle={-45} textAnchor="end" height={50} />
                <YAxis tick={{ fontSize: 11 }} stroke="hsl(var(--muted-foreground))" width={35} axisLine={false} tickLine={false} />
                <Tooltip contentStyle={{ backgroundColor: "hsl(var(--card))", border: "1px solid hsl(var(--border))", borderRadius: "8px", fontSize: "12px" }} />
                <Area type="monotone" dataKey="positive" name="Positive" stroke="hsl(var(--positive))" strokeWidth={2} fill="url(#posGrad)" dot={{ fill: "hsl(var(--positive))", r: 3 }} />
                <Area type="monotone" dataKey="neutral" name="Neutral" stroke="hsl(var(--neutral))" strokeWidth={2} fill="url(#neuGrad)" dot={{ fill: "hsl(var(--neutral))", r: 3 }} />
                <Area type="monotone" dataKey="negative" name="Negative" stroke="hsl(var(--negative))" strokeWidth={2} fill="url(#negGrad)" dot={{ fill: "hsl(var(--negative))", r: 3 }} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Key Criteria - sentiment spectrum bars */}
        <div className="rounded-lg border border-border bg-card p-4">
          <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-4">
            Key Criteria
          </h4>
          <div className="flex flex-col gap-3">
            {criteriaData.map(({ criterion, positive, negative, neutral, total }) => (
              <CriteriaItem key={criterion} criterion={criterion} positive={positive} negative={negative} neutral={neutral} total={total} />
            ))}
          </div>
        </div>

      {/* Webshops now shown in ProductPage right column */}

      {/* Good mentions */}
      {positiveInsights.length > 0 && (
        <div className="rounded-lg border border-sentiment-positive/20 bg-sentiment-positive/5 p-4">
          <h4 className="text-xs font-semibold text-sentiment-positive uppercase tracking-wider mb-3 flex items-center gap-1.5">
            <ThumbsUp className="h-3.5 w-3.5" />
            What Reviewers Liked
          </h4>
          <ul className="space-y-1.5">
            {positiveInsights.map((insight) => (
              <li key={insight.id} className="flex items-center justify-between text-sm">
                <span className="text-foreground">{insight.label}</span>
                <span className="text-xs text-muted-foreground">({insight.mention_count})</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Bad mentions */}
      {negativeInsights.length > 0 && (
        <div className="rounded-lg border border-sentiment-negative/20 bg-sentiment-negative/5 p-4">
          <h4 className="text-xs font-semibold text-sentiment-negative uppercase tracking-wider mb-3 flex items-center gap-1.5">
            <ThumbsDown className="h-3.5 w-3.5" />
            What Reviewers Disliked
          </h4>
          <ul className="space-y-1.5">
            {negativeInsights.map((insight) => (
              <li key={insight.id} className="flex items-center justify-between text-sm">
                <span className="text-foreground">{insight.label}</span>
                <span className="text-xs text-muted-foreground">({insight.mention_count})</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
    </>
  );
}
