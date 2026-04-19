import { useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { fetchProductById } from "@/lib/sqlite-queries";
import { ScoreBadge } from "@/components/ScoreBadge";
import { ReviewInsights } from "@/components/ReviewInsights";
import { BenchmarksDisplay } from "@/components/BenchmarksDisplay";
import { Navbar } from "@/components/Navbar";
import { Loader2, Smartphone, Store, ExternalLink, Settings, ShoppingBag } from "lucide-react";

const ProductPage = () => {
  const { id } = useParams<{ id: string }>();

  console.log("ProductPage rendered with id:", id);

  const { data: product, isLoading, error } = useQuery({
    queryKey: ["product", id],
    queryFn: () => fetchProductById(id!),
    enabled: !!id,
  });

  console.log("Product query:", { product, isLoading, error });

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="h-6 w-6 animate-spin text-primary" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <p className="text-muted-foreground">Error loading product: {String(error)}</p>
      </div>
    );
  }

  const specs = (product.specs as Record<string, unknown>) || {};
  const webshops = (product.product_webshops || []).map((w) => ({
    id: String(w.id),
    webshop_name: String(w.webshop_name),
    webshop_url: w.webshop_url ? String(w.webshop_url) : null,
    price_eur: Number(w.price_eur || product.price_eur),
    review_count: Number(w.review_count),
  }));

  const formatSpecValue = (value: unknown) => {
    if (value === null || value === undefined) return "-";
    if (typeof value === "string") return value;
    if (typeof value === "number" || typeof value === "boolean") return String(value);
    if (Array.isArray(value)) return value.map((item) => formatSpecValue(item)).join(", ");
    try {
      return JSON.stringify(value, null, 2);
    } catch {
      return String(value);
    }
  };
  const insights = (product.review_insights || []).map((r) => ({
    id: String(r.id || `${r.label}-${r.sentiment}`),
    label: String(r.label),
    sentiment: String(r.sentiment),
    mention_count: Number(r.mention_count),
  }));
  const timeline = (product.review_timeline || []).map((t) => ({
    month: String(t.month || t.year || ""),
    sentiment: String(t.sentiment),
    count: Number(t.count),
  }));

  return (
    <div className="min-h-screen bg-background">
      <Navbar />

      <div className="max-w-6xl mx-auto px-4 py-8">
        <div className="grid md:grid-cols-2 gap-8">
          {/* LEFT COLUMN: Image + Review Insights */}
          <div className="flex flex-col gap-6">
            {/* Image */}
            <div className="flex items-center justify-center rounded-lg bg-card border border-border p-8">
              {product.image_url ? (
                <img src={product.image_url as string} alt={String(product.name)} className="max-h-72 object-contain" />
              ) : (
                <Smartphone className="h-32 w-32 text-muted-foreground/30" />
              )}
            </div>

            {/* Review Insights */}
            {insights.length > 0 && (
              <ReviewInsights insights={insights} webshops={webshops} timeline={timeline} />
            )}
          </div>

          {/* RIGHT COLUMN: Info + Webshops + Specs */}
          <div className="flex flex-col gap-4">
            <p className="text-xs text-muted-foreground font-medium uppercase tracking-wider">{String(product.brand)}</p>
            <h1 className="text-2xl md:text-3xl font-bold font-display text-foreground">{String(product.name)}</h1>

            <div className="flex items-center gap-4">
              <ScoreBadge score={Number(product.score)} size="lg" />
              <span className="text-2xl font-bold text-primary font-display">
                €{Number(product.display_price_eur || product.price_eur).toLocaleString("de-DE", { minimumFractionDigits: 2 })}
              </span>
            </div>

            {product.description && (
              <p className="text-sm text-muted-foreground leading-relaxed">{String(product.description)}</p>
            )}

            {/* Webshops */}
            {webshops.length > 0 && (
              <div>
                <h3 className="text-sm font-semibold text-foreground mb-2 flex items-center gap-2">
                  <ShoppingBag className="h-4 w-4 text-primary" />
                  Webshops
                </h3>
                <div className="grid grid-cols-1 gap-2">
                  {webshops
                    .sort((a, b) => a.price_eur - b.price_eur)
                    .map((shop) => {
                      const content = (
                        <div className="flex items-center justify-between rounded-lg border border-border bg-muted px-4 py-3 hover:border-primary/50 hover:shadow-[0_0_12px_-2px_hsl(var(--primary)/0.3)] transition-all duration-200">
                          <div className="flex flex-col">
                            <span className="text-xs uppercase tracking-wider text-foreground font-semibold">{shop.webshop_name}</span>
                            <span className="text-[11px] text-muted-foreground">{shop.review_count.toLocaleString()} reviews</span>
                          </div>
                          <span className="text-base font-bold text-primary font-display">
                            €{shop.price_eur.toLocaleString("de-DE", { minimumFractionDigits: 2 })}
                          </span>
                        </div>
                      );
                      return shop.webshop_url ? (
                        <a key={shop.id} href={shop.webshop_url} target="_blank" rel="noopener noreferrer" className="block">
                          {content}
                        </a>
                      ) : (
                        <div key={shop.id}>{content}</div>
                      );
                    })}
                </div>
              </div>
            )}

            {/* Benchmarks */}
            {product.benchmarks && product.benchmarks.length > 0 && (
              <BenchmarksDisplay benchmarks={product.benchmarks as any} />
            )}

            {/* Specifications */}
            {Object.keys(specs).length > 0 && (
              <div className="flex flex-col gap-4">
                <h3 className="text-sm font-semibold text-foreground flex items-center gap-2">
                  <Settings className="h-4 w-4 text-primary" />
                  Specifications
                </h3>
                {Object.entries(specs).map(([category, features]) => (
                  <div key={category} className="flex flex-col gap-2">
                    <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                      {category}
                    </h4>
                    <div className="grid grid-cols-2 gap-2">
                      {Object.entries(features).map(([feature, value]) => (
                        <div key={`${category}-${feature}`} className="flex flex-col rounded-md bg-muted px-3 py-2">
                          <span className="text-[10px] uppercase tracking-wider text-muted-foreground font-medium">
                            {feature}
                          </span>
                          <span className="text-sm font-medium text-foreground">
                            {formatSpecValue(value)}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default ProductPage;
