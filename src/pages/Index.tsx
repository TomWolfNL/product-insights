import { SearchBar } from "@/components/SearchBar";
import { Navbar } from "@/components/Navbar";

const Index = () => {
  return (
    <div className="min-h-screen flex flex-col">
      <Navbar />

      {/* Hero - full page background */}
      <section className="flex-1 gradient-hero px-4 py-20 md:py-32 flex items-center justify-center">
        <div className="max-w-4xl mx-auto text-center flex flex-col items-center gap-6">
          <h1 className="text-3xl md:text-5xl font-bold font-display leading-tight" style={{ color: "hsl(220 20% 95%)" }}>
            Find the perfect product,<br />
            <span className="bg-gradient-to-r from-primary to-accent bg-clip-text text-transparent">
              backed by real reviews
            </span>
          </h1>
          <p className="text-sm md:text-base max-w-lg" style={{ color: "hsl(220 15% 70%)" }}>
            Search across thousands of products with AI-powered review analysis. Scores based on real user feedback.
          </p>
          <SearchBar variant="hero" placeholder="Search for smartphones, tablets, laptops..." />
        </div>
      </section>
    </div>
  );
};

export default Index;
