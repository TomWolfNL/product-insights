import { Link } from "react-router-dom";
import { ScoreBadge } from "./ScoreBadge";
import { Smartphone } from "lucide-react";

interface ProductCardProps {
  id: string;
  name: string;
  brand: string;
  priceEur: number;
  score: number;
  imageUrl: string | null;
  categorySlug?: string;
}

export function ProductCard({ id, name, brand, priceEur, score, imageUrl, categorySlug }: ProductCardProps) {
  return (
    <Link
      to={`/product/${id}`}
      className="group flex flex-col rounded-lg border border-border bg-card shadow-card transition-all duration-200 hover:shadow-card-hover hover:border-primary/30 overflow-hidden"
    >
      <div className="flex items-center justify-center h-40 bg-muted/50 p-4">
        {imageUrl ? (
          <img src={imageUrl} alt={name} className="h-full object-contain" />
        ) : (
          <Smartphone className="h-16 w-16 text-muted-foreground/40" />
        )}
      </div>
      <div className="flex flex-col gap-2 p-4">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <p className="text-xs text-muted-foreground font-medium uppercase tracking-wider">{brand}</p>
            <h3 className="text-sm font-semibold text-card-foreground line-clamp-2 mt-0.5">{name}</h3>
          </div>
          <ScoreBadge score={score} size="sm" />
        </div>
        <p className="text-lg font-bold text-primary font-display">
          €{priceEur.toLocaleString("de-DE", { minimumFractionDigits: 2 })}
        </p>
      </div>
    </Link>
  );
}
