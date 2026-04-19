from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from reviews_scraper_mediamarkt import scrape_mediamarkt_reviews


BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "scraped_data"
OUTPUT_DIR.mkdir(exist_ok=True)

HEADERS = {"User-Agent": "Mozilla/5.0"}

PRODUCTS: List[Dict[str, Any]] = [
    {
        "name": "Apple iPhone 17",
        "gsmarena_url": "https://www.gsmarena.com/apple_iphone_17-14050.php",
        "webshops": {
            "mediamarkt": "https://www.mediamarkt.nl/en/product/_apple-iphone-17-5g-256-gb-black-256-gb-black-1890775.html",
        },
    },
    {
        "name": "Apple iPhone 17 Pro",
        "gsmarena_url": "https://www.gsmarena.com/apple_iphone_17_pro-14049.php",
        "webshops": {
            "mediamarkt": "https://www.mediamarkt.nl/en/product/_apple-iphone-17-pro-5g-256-gb-256-gb-blue-1890787.html",
        },
    },
    {
        "name": "Apple iPhone 17 Pro Max",
        "gsmarena_url": "https://www.gsmarena.com/apple_iphone_17_pro_max-13964.php",
        "webshops": {
            "mediamarkt": "https://www.mediamarkt.nl/en/product/_apple-iphone-17-pro-max-5g-256-gb-cosmic-orange-1890795.html",
        },
    },
    {
        "name": "Samsung Galaxy S25 FE",
        "gsmarena_url": "https://www.gsmarena.com/samsung_galaxy_s25_fe_5g-14042.php",
        "webshops": {
            "mediamarkt": "https://www.mediamarkt.nl/en/product/_-1888631.html",
        },
    },
    {
        "name": "Samsung Galaxy S26",
        "gsmarena_url": "https://www.gsmarena.com/samsung_galaxy_s26_5g-14456.php",
        "webshops": {
            "mediamarkt": "https://www.mediamarkt.nl/en/product/_samsung-galaxy-s26-5g-256-gb-black-1896657.html",
        },
    },
    {
        "name": "Samsung Galaxy S26+",
        "gsmarena_url": "https://www.gsmarena.com/samsung_galaxy_s26+_5g-14457.php",
        "webshops": {
            "mediamarkt": "https://www.mediamarkt.nl/en/product/_samsung-galaxy-s26-5g-256-gb-black-1896665.html",
        },
    },
    {
        "name": "Samsung Galaxy S26 Ultra",
        "gsmarena_url": "https://www.gsmarena.com/samsung_galaxy_s26_ultra_5g-14320.php",
        "webshops": {
            "mediamarkt": "https://www.mediamarkt.nl/en/product/_samsung-galaxy-s26-ultra-5g-256-gb-black-1896676.html",
        },
    },
    {
        "name": "Samsung Galaxy A56",
        "gsmarena_url": "https://www.gsmarena.com/samsung_galaxy_a56-13603.php",
        "webshops": {
            "mediamarkt": "https://www.mediamarkt.nl/en/product/_galaxy-a56-5g-1880175.html",
        },
    },
    {
        "name": "Samsung Galaxy A54",
        "gsmarena_url": "https://www.gsmarena.com/samsung_galaxy_a54-12070.php",
        "webshops": {
            "mediamarkt": "https://www.mediamarkt.nl/en/product/_galaxy-a54-5g-128-gb-black-104205017.html",
        },
    },
    {
        "name": "Samsung Galaxy A33",
        "gsmarena_url": "https://www.gsmarena.com/samsung_galaxy_a33_5g-11429.php",
        "webshops": {
            "mediamarkt": "https://www.mediamarkt.nl/en/product/_galaxy-a33-5g-128-gb-black-ee-98621190.html",
        },
    },
    {
        "name": "Samsung Galaxy A16",
        "gsmarena_url": "https://www.gsmarena.com/samsung_galaxy_a16-13383.php",
        "webshops": {
            "mediamarkt": "https://www.mediamarkt.nl/en/product/_galaxy-a16-4g-lte-128gb-black-1874426.html",
        },
    },
    {
        "name": "Samsung Galaxy A13",
        "gsmarena_url": "https://www.gsmarena.com/samsung_galaxy_a13-11402.php",
        "webshops": {
            "mediamarkt": "https://www.mediamarkt.nl/en/product/_galaxy-a13-96854348.html",
        },
    },
    {
        "name": "Xiaomi Redmi A5",
        "gsmarena_url": "https://www.gsmarena.com/xiaomi_redmi_a5_4g-13737.php",
        "webshops": {
            "mediamarkt": "https://www.mediamarkt.nl/en/product/_redmi-a5-3gb-ram-64gb-rom-black-1881254.html",
        },
    },
    {
        "name": "Xiaomi Redmi Note 14 4G",
        "gsmarena_url": "https://www.gsmarena.com/xiaomi_redmi_note_14_4g_(global)-13616.php",
        "webshops": {
            "mediamarkt": "https://www.mediamarkt.nl/en/product/_redmi-note-14-4g-256gb-midnight-black-1877176.html",
        },
    },
    {
        "name": "Xiaomi Redmi Note 12",
        "gsmarena_url": "https://www.gsmarena.com/xiaomi_redmi_note_12-12063.php",
        "webshops": {
            "mediamarkt": "https://www.mediamarkt.nl/en/product/_redmi-note-12-128gb-gray-104204808.html",
        },
    },
    {
        "name": "Fairphone 6",
        "gsmarena_url": "https://www.gsmarena.com/fairphone_6-13955.php",
        "webshops": {
            "mediamarkt": "https://www.mediamarkt.nl/en/product/_fairphone-fairphone-gen-6-256-gb-green-1895813.html",
        },
    },
    {
        "name": "Oppo A96",
        "gsmarena_url": "https://www.gsmarena.com/oppo_a96-11434.php",
        "webshops": {
            "mediamarkt": "https://www.mediamarkt.nl/en/product/_a96-128gb-starry-black-94606490.html",
        },
    },
]


def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9+]+", "_", text)
    return text.strip("_") or "product"



def extract_gsmarena_image_url(soup: BeautifulSoup, page_url: str) -> str | None:
    og_image = soup.select_one('meta[property="og:image"]')
    if og_image and og_image.get("content"):
        return urljoin(page_url, og_image["content"].strip())

    main_image = soup.select_one("div.specs-photo-main img")
    if main_image and main_image.get("src"):
        return urljoin(page_url, main_image["src"].strip())

    picture_source = soup.select_one("picture img")
    if picture_source and picture_source.get("src"):
        return urljoin(page_url, picture_source["src"].strip())

    return None



def fetch_gsmarena_specs(url: str) -> Dict[str, Any]:
    response = requests.get(url, headers=HEADERS, timeout=30)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    name_node = soup.select_one("h1.specs-phone-name-title")
    if name_node is None:
        raise ValueError(f"Could not find product name on GSMArena page: {url}")

    raw_specs: Dict[str, Dict[str, str]] = {}

    for table in soup.select("#specs-list table"):
        section_node = table.select_one("th")
        if section_node is None:
            continue

        section = section_node.get_text(" ", strip=True)
        if section == "Network":
            continue

        current = None
        raw_specs[section] = {}

        for row in table.select("tr"):
            k = row.select_one(".ttl")
            v = row.select_one(".nfo")
            if not (k and v):
                continue

            key = k.get_text(" ", strip=True).replace(" ", "")
            val = v.get_text(" ", strip=True)

            if key:
                current = key
                raw_specs[section][key] = val
            elif current:
                raw_specs[section][current] += " | " + val
            else:
                raw_specs[section]["_"] = val

    ordered_specs: Dict[str, Dict[str, Any]] = {}
    if "Our Tests" in raw_specs:
        our_tests = raw_specs.pop("Our Tests")

        benchmarks: Dict[str, Any] = {}
        performance_antutu: Dict[str, str] = {}
        other_tests: Dict[str, str] = {}

        performance_keys = {"antutu", "geekbench", "3dmark"}

        for key, val in our_tests.items():
            normalized_key = re.sub(r"[^a-z0-9]+", "", key.lower())

            if normalized_key in performance_keys:
                performance_antutu[key] = val
            else:
                other_tests[key] = val

        if performance_antutu:
            benchmarks["Performance AnTuTu"] = performance_antutu

        benchmarks.update(other_tests)
        ordered_specs["Benchmarks"] = benchmarks

    ordered_specs.update(raw_specs)

    data: Dict[str, Any] = {
        "image_url": extract_gsmarena_image_url(soup, url),
        "specs": ordered_specs,
    }

    return data



def scrape_product(product: Dict[str, Any]) -> Dict[str, Any]:
    product_name = product["name"]
    gsmarena_url = product["gsmarena_url"]

    result: Dict[str, Any] = {
        "product_name": product_name,
        "gsmarena": fetch_gsmarena_specs(gsmarena_url),
        "webshops": {},
    }

    for webshop_name, webshop_url in product.get("webshops", {}).items():
        if webshop_name == "mediamarkt":
            result["webshops"][webshop_name] = scrape_mediamarkt_reviews(webshop_url)
        else:
            result["webshops"][webshop_name] = {
                "url": webshop_url,
                "error": f"No scraper configured for webshop '{webshop_name}'",
            }

    return result



def save_product_json(product_data: Dict[str, Any]) -> Path:
    filename = f"{slugify(product_data['product_name'])}.json"
    output_path = OUTPUT_DIR / filename

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(product_data, f, ensure_ascii=False, indent=2)

    return output_path



def main() -> None:
    for product in PRODUCTS:
        scraped = scrape_product(product)
        saved_path = save_product_json(scraped)
        print(f"Saved: {saved_path}")


if __name__ == "__main__":
    main()
