# Product Insights

## Install & run the webapp

- `npm install` install packages from package.json
- `npm run dev` unoptimized or `npm run dev` optimized but takes longer to load

## Generate new database

- `python -m venv .venv` create Python environment
- `pip install -r scraping_and_analysis/requirements.txt` install packages from requirements.txt
- `python scraping_and_analysis/scraping.py` scrape categories, products, webshops, and reviews
- `python scraping_and_analysis/analysis.py` create product based analysis