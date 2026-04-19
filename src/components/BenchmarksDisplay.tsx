import { BarChart3 } from "lucide-react";
import { useCountUp } from "@/hooks/useCountUp";

interface Benchmark {
  antutu_score: number | null;
  antutu_percentile: number | null;
  geekbench_score: number | null;
  geekbench_percentile: number | null;
  three_dmark_score: number | null;
  three_dmark_percentile: number | null;
  display_brightness_nits: number | null;
  display_percentile: number | null;
  loudspeaker_lufs: number | null;
  loudspeaker_percentile: number | null;
  battery_active_use_hours: number | null;
  battery_percentile: number | null;
}

interface BenchmarksDisplayProps {
  benchmarks: Benchmark[];
}

function formatBenchmarkValue(value: number | null, label: string): string {
  if (value === null) return "—";
  
  switch (label) {
    case "AnTuTu":
    case "GeekBench":
    case "3DMark":
      return Math.round(value).toLocaleString();
    case "Display Brightness":
      return `${Math.round(value)} nits`;
    case "Loudspeaker":
      return `${value.toFixed(1)} LUFS`;
    case "Battery Life":
      return `${value.toFixed(1)}h`;
    default:
      return String(value);
  }
}

const style = `
  @keyframes fillBar {
    from {
      width: 0%;
    }
    to {
      width: var(--bar-width);
    }
  }
  
  .animate-fill-bar {
    animation: fillBar 1.2s ease-out forwards;
  }
`;

export function BenchmarksDisplay({ benchmarks }: BenchmarksDisplayProps) {
  if (!benchmarks || benchmarks.length === 0) return null;

  const benchmark = benchmarks[0];
  
  const benchmarksList = [
    {
      label: "AnTuTu",
      value: benchmark.antutu_score,
      percentile: benchmark.antutu_percentile,
    },
    {
      label: "GeekBench",
      value: benchmark.geekbench_score,
      percentile: benchmark.geekbench_percentile,
    },
    {
      label: "3DMark",
      value: benchmark.three_dmark_score,
      percentile: benchmark.three_dmark_percentile,
    },
    {
      label: "Display Brightness",
      value: benchmark.display_brightness_nits,
      percentile: benchmark.display_percentile,
    },
    {
      label: "Loudspeaker",
      value: benchmark.loudspeaker_lufs,
      percentile: benchmark.loudspeaker_percentile,
    },
    {
      label: "Battery Life",
      value: benchmark.battery_active_use_hours,
      percentile: benchmark.battery_percentile,
    },
  ];

  // Filter only benchmarks that have values
  const availableBenchmarks = benchmarksList.filter((b) => b.value !== null && b.value !== undefined);

  if (availableBenchmarks.length === 0) return null;

  return (
    <>
      <style>{style}</style>
      <div className="flex flex-col gap-4">
        <h3 className="text-sm font-semibold text-foreground flex items-center gap-2">
          <BarChart3 className="h-4 w-4 text-primary" />
          Benchmarks
        </h3>
        <div className="grid grid-cols-2 gap-2">
          {availableBenchmarks.map(({ label, value, percentile }) => {
            const percentileNum = percentile || 0;
            const barWidth = Math.max(percentileNum, 5);
            const animatedPercentile = useCountUp(percentileNum, 1200);
            const formattedValue = formatBenchmarkValue(value, label);
            
            return (
              <div key={label} className="flex flex-col rounded-md bg-muted px-3 py-2">
                <span className="text-[10px] uppercase tracking-wider text-muted-foreground font-medium">
                  {label}
                </span>
                <div className="relative h-8 bg-primary rounded-md overflow-hidden mt-2">
                  <div
                    className="h-full bg-gray-800 flex items-center pl-2 animate-fill-bar"
                    style={{ 
                      "--bar-width": `${barWidth}%`,
                    } as React.CSSProperties}
                  >
                    <span className="text-xs font-semibold text-primary-foreground whitespace-nowrap">
                      {formattedValue}
                    </span>
                  </div>
                </div>
                <span className="text-[10px] text-muted-foreground mt-1">
                  better than {animatedPercentile}%
                </span>
              </div>
            );
          })}
        </div>
      </div>
    </>
  );
}
