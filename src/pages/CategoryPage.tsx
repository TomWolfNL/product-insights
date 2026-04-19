import { useState, useMemo, useEffect } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { fetchProducts, fetchBrandsByCategory } from "@/lib/sqlite-queries";
import { ProductCard } from "@/components/ProductCard";
import { ProductFilters } from "@/components/ProductFilters";
import { SearchBar } from "@/components/SearchBar";
import { SortSelect } from "@/components/SortSelect";
import { Navbar } from "@/components/Navbar";
import { Loader2, SlidersHorizontal, X } from "lucide-react";
import { Button } from "@/components/ui/button";

type SortOption = "score_desc" | "score_asc" | "price_asc" | "price_desc";

const CategoryPage = () => {
  const { slug } = useParams<{ slug: string }>();
  const [searchParams] = useSearchParams();
  const brandFromUrl = searchParams.get("brand");

  const [search, setSearch] = useState("");
  const [sortBy, setSortBy] = useState<SortOption>("score_desc");
  const [selectedBrands, setSelectedBrands] = useState<string[]>(brandFromUrl ? [brandFromUrl] : []);
  const [priceRange, setPriceRange] = useState<[number, number]>([0, 2000]);
  const [minScore, setMinScore] = useState(0);
  const [showFilters, setShowFilters] = useState(false);

  useEffect(() => {
    if (brandFromUrl) setSelectedBrands([brandFromUrl]);
  }, [brandFromUrl]);

  const { data: products, isLoading } = useQuery({
    queryKey: ["products", slug, sortBy],
    queryFn: () => fetchProducts({ categorySlug: slug, sortBy }),
    enabled: !!slug,
  });

  const { data: brands = [] } = useQuery({
    queryKey: ["brands", slug],
    queryFn: () => fetchBrandsByCategory(slug!),
    enabled: !!slug,
  });

  const getEffectivePrice = (p: any) => {
    if (p.product_webshops && p.product_webshops.length > 0) {
      const webshopPrices = p.product_webshops
        .map((w: any) => Number(w.price_eur || 0))
        .filter((v: number) => !Number.isNaN(v) && v > 0);
      if (webshopPrices.length > 0) return Math.min(...webshopPrices);
    }
    return Number(p.price_eur || 0);
  };

  const maxPrice = useMemo(() => {
    if (!products?.length) return 2000;
    return Math.ceil(Math.max(...products.map((p) => getEffectivePrice(p))) / 100) * 100;
  }, [products]);

  const filteredProducts = useMemo(() => {
    if (!products) return [];
    return products.filter((p) => {
      const name = String(p.name || "");
      const brand = String(p.brand || "");
      const price = getEffectivePrice(p);
      const score = Number(p.score);
      if (search && !name.toLowerCase().includes(search.toLowerCase()) && !brand.toLowerCase().includes(search.toLowerCase())) return false;
      if (price < priceRange[0] || price > priceRange[1]) return false;
      if (selectedBrands.length > 0 && !selectedBrands.includes(brand)) return false;
      if (score < minScore) return false;
      return true;
    });
  }, [products, search, priceRange, selectedBrands, minScore]);

  const categoryName = products?.[0]?.product_categories?.name || slug;

  return (
    <div className="min-h-screen bg-background">
      <Navbar />

      {/* Sub-header */}
      <div className="border-b border-border bg-card px-4 py-3">
        <div className="max-w-7xl mx-auto flex items-center gap-4">
          <h1 className="text-lg font-bold font-display text-foreground">{categoryName}</h1>
          <div className="flex-1 max-w-md ml-auto">
            <SearchBar
              initialValue={search}
              onSearch={setSearch}
              placeholder={`Search in ${categoryName}...`}
            />
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 py-6">
        <div className="flex items-center justify-between mb-6">
          <p className="text-sm text-muted-foreground">
            {filteredProducts.length} product{filteredProducts.length !== 1 ? "s" : ""}
          </p>
          <div className="flex items-center gap-3">
            <Button
              variant="outline"
              size="sm"
              className="md:hidden"
              onClick={() => setShowFilters(!showFilters)}
            >
              {showFilters ? <X className="h-4 w-4" /> : <SlidersHorizontal className="h-4 w-4" />}
              Filters
            </Button>
            <SortSelect value={sortBy} onChange={setSortBy} />
          </div>
        </div>

        <div className="flex gap-6">
          <aside className={`w-60 shrink-0 ${showFilters ? "block" : "hidden"} md:block`}>
            <div className="sticky top-20 rounded-lg border border-border bg-card p-4">
              <ProductFilters
                brands={brands as string[]}
                selectedBrands={selectedBrands}
                onBrandsChange={setSelectedBrands}
                priceRange={priceRange}
                maxPrice={maxPrice}
                onPriceChange={setPriceRange}
                minScore={minScore}
                onMinScoreChange={setMinScore}
              />
            </div>
          </aside>

          <div className="flex-1">
            {isLoading ? (
              <div className="flex items-center justify-center py-16">
                <Loader2 className="h-6 w-6 animate-spin text-primary" />
              </div>
            ) : filteredProducts.length === 0 ? (
              <div className="text-center py-16">
                <p className="text-muted-foreground">No products found matching your filters.</p>
              </div>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                {filteredProducts.map((product) => (
                  <ProductCard
                    key={String(product.id)}
                    id={String(product.id)}
                    name={String(product.name)}
                    brand={String(product.brand)}
                    priceEur={getEffectivePrice(product)}
                    score={Number(product.score)}
                    imageUrl={product.image_url as string | null}
                    categorySlug={slug}
                  />
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default CategoryPage;
