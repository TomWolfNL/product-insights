import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

type SortOption = "score_desc" | "score_asc" | "price_asc" | "price_desc";

interface SortSelectProps {
  value: SortOption;
  onChange: (value: SortOption) => void;
}

export function SortSelect({ value, onChange }: SortSelectProps) {
  return (
    <Select value={value} onValueChange={(v) => onChange(v as SortOption)}>
      <SelectTrigger className="w-[180px] bg-card">
        <SelectValue placeholder="Sort by" />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value="score_desc">Score: High → Low</SelectItem>
        <SelectItem value="score_asc">Score: Low → High</SelectItem>
        <SelectItem value="price_asc">Price: Low → High</SelectItem>
        <SelectItem value="price_desc">Price: High → Low</SelectItem>
      </SelectContent>
    </Select>
  );
}
