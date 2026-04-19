import { Search } from "lucide-react";
import { useState, useEffect, useRef } from "react";
import { useNavigate, Link } from "react-router-dom";
import { searchAllProducts } from "@/lib/sqlite-queries";
import { ScoreBadge } from "./ScoreBadge";

interface SearchBarProps {
  initialValue?: string;
  onSearch?: (query: string) => void;
  placeholder?: string;
  variant?: "hero" | "compact";
}

interface Suggestion {
  id: string;
  name: string;
  brand: string;
  score: number;
  price_eur: number;
  product_categories?: { slug: unknown } | null;
}

export function SearchBar({ initialValue = "", onSearch, placeholder = "Search products...", variant = "compact" }: SearchBarProps) {
  const [query, setQuery] = useState(initialValue);
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();
  const wrapperRef = useRef<HTMLDivElement>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout>>();

  useEffect(() => {
    setQuery(initialValue);
  }, [initialValue]);

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);

    if (query.trim().length < 2) {
      setSuggestions([]);
      setShowSuggestions(false);
      return;
    }

    debounceRef.current = setTimeout(async () => {
      setLoading(true);
      try {
        const results = await searchAllProducts(query.trim());
        const mapped: Suggestion[] = (results || []).slice(0, 6).map((r) => ({
          id: String(r.id),
          name: String(r.name).trim(),
          brand: String(r.brand).trim(),
          score: Number(r.score),
          price_eur: Number(r.price_eur),
          product_categories: r.product_categories,
        }));
        setSuggestions(mapped);
        setShowSuggestions(true);
      } catch {
        setSuggestions([]);
      } finally {
        setLoading(false);
      }
    }, 250);

    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [query]);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target as Node)) {
        setShowSuggestions(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setShowSuggestions(false);
    if (onSearch) {
      onSearch(query);
    } else if (query.trim()) {
      navigate(`/search?q=${encodeURIComponent(query.trim())}`);
    }
  };

  const isHero = variant === "hero";

  return (
    <form onSubmit={handleSubmit} className="w-full">
      <div ref={wrapperRef} className={`relative flex flex-col items-center ${isHero ? "max-w-2xl mx-auto" : ""}`}>
        <div className="relative w-full">
          <Search className={`absolute left-4 top-1/2 -translate-y-1/2 text-muted-foreground ${isHero ? "h-5 w-5" : "h-4 w-4"} z-10`} />
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onFocus={() => suggestions.length > 0 && setShowSuggestions(true)}
            placeholder={placeholder}
            className={`w-full rounded-lg border border-input bg-card text-card-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring transition-shadow ${
              isHero ? "pl-12 pr-4 py-4 text-base" : "pl-10 pr-4 py-2.5 text-sm"
            }`}
          />
        </div>

        {/* Suggestions dropdown */}
        {showSuggestions && suggestions.length > 0 && (
          <div className="absolute top-full left-0 right-0 mt-1 rounded-lg border border-border bg-card shadow-lg z-50 overflow-hidden">
            {suggestions.map((s) => (
              <Link
                key={s.id}
                to={`/product/${s.id}`}
                onClick={() => setShowSuggestions(false)}
                className="flex items-center justify-between px-4 py-3 hover:bg-muted/50 transition-colors border-b border-border last:border-b-0 text-left"
              >
                <div className="flex flex-col min-w-0 gap-0 text-left">
                  <span className="text-sm font-medium text-foreground leading-tight">{s.name}</span>
                  <span className="text-xs text-muted-foreground leading-tight">{s.brand}</span>
                </div>
                <div className="flex flex-col items-end gap-1 ml-2">
                  <ScoreBadge score={s.score} size="sm" />
                  <span className="text-xs font-semibold text-primary">
                    €{s.price_eur.toLocaleString("de-DE", { minimumFractionDigits: 2 })}
                  </span>
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>
    </form>
  );
}
