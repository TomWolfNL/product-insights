import { useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { searchAllProducts } from "@/lib/sqlite-queries";
import { ProductCard } from "@/components/ProductCard";
import { SearchBar } from "@/components/SearchBar";
import { Navbar } from "@/components/Navbar";
import { Loader2 } from "lucide-react";

const SearchPage = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const query = searchParams.get("q") || "";

  const { data: products, isLoading } = useQuery({
    queryKey: ["search", query],
    queryFn: () => searchAllProducts(query),
    enabled: query.length > 0,
  });

  const handleSearch = (q: string) => {
    setSearchParams({ q });
  };

  return (
    <div className="min-h-screen bg-background">
      <Navbar />

      <div className="border-b border-border bg-card px-4 py-3">
        <div className="max-w-5xl mx-auto">
          <SearchBar initialValue={query} onSearch={handleSearch} placeholder="Search all products..." />
        </div>
      </div>

      <div className="max-w-5xl mx-auto px-4 py-8">
        {query && (
          <p className="text-sm text-muted-foreground mb-6">
            {isLoading ? "Searching..." : `${products?.length || 0} results for "${query}"`}
          </p>
        )}

        {isLoading ? (
          <div className="flex items-center justify-center py-16">
            <Loader2 className="h-6 w-6 animate-spin text-primary" />
          </div>
        ) : !query ? (
          <p className="text-center text-muted-foreground py-16">Enter a search term to find products.</p>
        ) : products?.length === 0 ? (
          <p className="text-center text-muted-foreground py-16">No products found for "{query}".</p>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            {products?.map((product) => (
              <ProductCard
                key={String(product.id)}
                id={String(product.id)}
                name={String(product.name)}
                brand={String(product.brand)}
                priceEur={Number(product.price_eur)}
                score={Number(product.score)}
                imageUrl={product.image_url as string | null}
                categorySlug={product.product_categories?.slug as string | undefined}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default SearchPage;
