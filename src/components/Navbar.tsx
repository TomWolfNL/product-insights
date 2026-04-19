import { Link, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { BarChart3 } from "lucide-react";
import { fetchCategories, fetchBrandsByCategory } from "@/lib/sqlite-queries";
import { useState, useRef, useCallback } from "react";

interface CategoryWithBrands {
  id: string;
  name: string;
  slug: string;
  icon: string | null;
}

function CategoryDropdown({ category, isActive }: { category: CategoryWithBrands; isActive: boolean }) {
  const [open, setOpen] = useState(false);
  const closeTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const { data: brands } = useQuery({
    queryKey: ["brands", category.slug],
    queryFn: () => fetchBrandsByCategory(category.slug),
  });

  const handleEnter = useCallback(() => {
    if (closeTimer.current) clearTimeout(closeTimer.current);
    setOpen(true);
  }, []);

  const handleLeave = useCallback(() => {
    closeTimer.current = setTimeout(() => setOpen(false), 150);
  }, []);

  return (
    <div
      className="relative"
      onMouseEnter={handleEnter}
      onMouseLeave={handleLeave}
    >
      <Link
        to={`/category/${category.slug}`}
        className={`text-sm font-medium transition-colors px-3 py-2 rounded-md inline-block ${
          isActive
            ? "text-primary bg-primary/10"
            : "text-muted-foreground hover:text-foreground hover:bg-muted/50"
        }`}
      >
        {category.name}
      </Link>

      {open && brands && brands.length > 0 && (
        <div className="absolute top-full left-0 mt-1 min-w-[200px] rounded-lg border border-border bg-card shadow-lg z-50 py-1">
          {brands.map((brand) => (
            <Link
              key={brand}
              to={`/category/${category.slug}?brand=${encodeURIComponent(brand)}`}
              onClick={() => setOpen(false)}
              className="block px-4 py-2 text-sm text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors"
            >
              {brand}
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}

export function Navbar() {
  const { slug } = useParams<{ slug?: string }>();

  const { data: categories } = useQuery({
    queryKey: ["categories"],
    queryFn: fetchCategories,
  });

  return (
    <nav className="sticky top-0 z-40 border-b border-border bg-card/95 backdrop-blur-sm py-0" style={{ overflow: 'visible' }}>
      <div className="max-w-7xl mx-auto flex items-center h-14 gap-0 px-4">
        {/* Logo */}
        <Link to="/" className="flex items-center gap-2 shrink-0">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg gradient-primary">
            <BarChart3 className="h-4.5 w-4.5 text-primary-foreground" />
          </div>
          <span className="text-base font-bold font-display text-foreground tracking-tight">
            Product Insights
          </span>
        </Link>

        {/* Divider */}
        <div className="h-6 w-px bg-border mx-5 shrink-0" />

        {/* Category links */}
        <div className="flex items-center gap-1">
          {categories?.map((cat) => (
            <CategoryDropdown
              key={cat.id}
              category={{
                id: cat.id,
                name: cat.name,
                slug: cat.slug,
                icon: cat.icon,
              }}
              isActive={slug === cat.slug}
            />
          ))}
        </div>
      </div>
    </nav>
  );
}
