import { Slider } from "@/components/ui/slider";
import { cn } from "@/lib/utils";

interface ProductFiltersProps {
  brands: string[];
  selectedBrands: string[];
  onBrandsChange: (brands: string[]) => void;
  priceRange: [number, number];
  maxPrice: number;
  onPriceChange: (range: [number, number]) => void;
  minScore: number;
  onMinScoreChange: (score: number) => void;
}

export function ProductFilters({
  brands,
  selectedBrands,
  onBrandsChange,
  priceRange,
  maxPrice,
  onPriceChange,
  minScore,
  onMinScoreChange,
}: ProductFiltersProps) {
  const toggleBrand = (brand: string) => {
    if (selectedBrands.includes(brand)) {
      onBrandsChange(selectedBrands.filter((b) => b !== brand));
    } else {
      onBrandsChange([...selectedBrands, brand]);
    }
  };

  return (
    <div className="flex flex-col gap-6">
      {/* Brands - first filter */}
      {brands.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold text-foreground mb-3">Brand</h3>
          <div className="flex flex-wrap gap-2">
            {brands.map((brand) => {
              const isSelected = selectedBrands.includes(brand);
              return (
                <button
                  key={brand}
                  onClick={() => toggleBrand(brand)}
                  className={cn(
                    "px-3 py-2 rounded-md text-xs font-medium border transition-colors",
                    isSelected
                      ? "bg-primary text-primary-foreground border-primary"
                      : "bg-card text-foreground border-border hover:border-primary/50"
                  )}
                >
                  {brand}
                </button>
              );
            })}
          </div>
        </div>
      )}

      {/* Price Range */}
      <div>
        <h3 className="text-sm font-semibold text-foreground mb-3">Price Range</h3>
        <Slider
          min={0}
          max={maxPrice}
          step={10}
          value={[priceRange[0], priceRange[1]]}
          onValueChange={(v) => onPriceChange([v[0], v[1]])}
          className="mb-2"
        />
        <div className="flex items-center justify-between text-xs text-muted-foreground">
          <span>€{priceRange[0]}</span>
          <span>€{priceRange[1]}</span>
        </div>
      </div>

      {/* Minimum Score */}
      <div>
        <h3 className="text-sm font-semibold text-foreground mb-3">Minimum Score</h3>
        <Slider
          min={0}
          max={10}
          step={0.5}
          value={[minScore]}
          onValueChange={(v) => onMinScoreChange(v[0])}
          className="mb-2"
        />
        <p className="text-xs text-muted-foreground">{minScore.toFixed(1)}+</p>
      </div>
    </div>
  );
}
