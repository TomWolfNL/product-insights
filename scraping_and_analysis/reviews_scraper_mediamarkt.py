from __future__ import annotations

import re
import sys
import time
from typing import Any, Dict, List, Optional

from playwright.sync_api import Locator, Page, sync_playwright


def safe_text(locator: Locator) -> str:
    try:
        if locator.count() == 0:
            return ""
        return locator.first.inner_text(timeout=2000).strip()
    except Exception:
        return ""


def accept_cookies(page: Page) -> None:
    for selector in [
        "#pwa-consent-layer-accept-all-button",
        "button#pwa-consent-layer-accept-all-button",
    ]:
        try:
            page.locator(selector).click(timeout=4000)
            return
        except Exception:
            pass


def scrape_product_info(page: Page) -> Dict[str, Any]:
    page.wait_for_selector("h1", state="attached", timeout=15000)

    price_whole = safe_text(page.locator('[data-test="branded-price-whole-value"]'))
    price_fraction = safe_text(page.locator('[data-test="branded-price-fractional-value"]'))

    price = price_whole
    if price_fraction:
        price = f"{price_whole}.{price_fraction}"

    return {
        "price": price,
    }


def slow_scroll_until_reviews_header(page: Page, max_steps: int = 120, step_px: int = 350) -> bool:
    header = page.locator("h3[aria-live='polite']").filter(has_text=re.compile(r"\breviews\b", re.I))

    for _ in range(max_steps):
        try:
            if header.count() > 0 and header.first.is_visible():
                header.first.scroll_into_view_if_needed(timeout=5000)
                return True
        except Exception:
            pass

        page.mouse.wheel(0, step_px)
        page.wait_for_timeout(350)

    return False


def wait_for_reviews_root(page: Page) -> bool:
    try:
        cards = page.locator("[data-test='single-review-card']")
        cards.first.wait_for(state="visible", timeout=15000)
        return True
    except Exception:
        return False


def expand_all_visible_reviews(page: Page) -> None:
    buttons = page.locator("[data-test='single-review-card'] [data-test='expand-button']")
    count = buttons.count()
    for i in range(count):
        btn = buttons.nth(i)
        try:
            expanded = btn.get_attribute("aria-expanded")
            if expanded != "true":
                btn.scroll_into_view_if_needed(timeout=2000)
                btn.click(timeout=2000)
                page.wait_for_timeout(150)
        except Exception:
            pass


def extract_card(card: Locator, page_number: int, idx: int) -> Dict[str, str]:
    rating = safe_text(card.locator("[data-test='mms-customer-rating-count']"))
    date = safe_text(card.locator("span").filter(has_text=re.compile(r"\d{2}/\d{2}/\d{4}")))
    title = safe_text(card.locator("p.ixvBRV, p.sc-59b6826e-0.ixvBRV"))
    body = safe_text(card.locator("[data-test='mms-review-full']"))
    variant = safe_text(card.locator("[data-test='mms-family-review']"))

    return {
        "page": str(page_number),
        "index_on_page": str(idx),
        "rating": rating,
        "date": date,
        "body": body,
        "variant": variant,
    }


def scrape_visible_review_page(page: Page, page_number: int) -> List[Dict[str, str]]:
    expand_all_visible_reviews(page)
    cards = page.locator("[data-test='single-review-card']")
    count = cards.count()
    rows: List[Dict[str, str]] = []

    for i in range(count):
        card = cards.nth(i)
        try:
            rows.append(extract_card(card, page_number, i + 1))
        except Exception:
            pass

    return rows


def current_signature(page: Page) -> str:
    first_card = page.locator("[data-test='single-review-card']").first
    return " | ".join(
        [
            safe_text(first_card.locator("[data-test='mms-customer-rating-count']")),
            safe_text(first_card.locator("span").filter(has_text=re.compile(r"\d{2}/\d{2}/\d{4}"))),
            safe_text(first_card.locator("[data-test='mms-review-full']")),
        ]
    )


def find_next_page_button(page: Page, n: int) -> Optional[Locator]:
    candidates = page.locator("button").filter(has_text=re.compile(rf"^{n}$"))
    count = candidates.count()

    for i in range(count):
        btn = candidates.nth(i)
        try:
            if btn.get_attribute("aria-disabled") == "true":
                continue
            text = btn.inner_text(timeout=1500).strip()
            if text != str(n):
                continue

            box = btn.bounding_box()
            if box and box["y"] > 400:
                return btn
        except Exception:
            continue

    for i in range(count):
        btn = candidates.nth(i)
        try:
            if btn.get_attribute("aria-disabled") != "true" and btn.inner_text(timeout=1500).strip() == str(n):
                return btn
        except Exception:
            continue

    return None


def click_next_page(page: Page, n: int) -> bool:
    btn = find_next_page_button(page, n)
    if btn is None or btn.count() == 0:
        return False

    before = current_signature(page)
    btn.scroll_into_view_if_needed(timeout=4000)
    page.wait_for_timeout(300)

    try:
        btn.click(timeout=4000)
    except Exception:
        btn.click(timeout=4000, force=True)

    deadline = time.time() + 12
    while time.time() < deadline:
        page.wait_for_timeout(400)
        after = current_signature(page)
        if after and after != before:
            return True
    return False


def dedupe_reviews(rows: List[Dict[str, str]]) -> List[Dict[str, str]]:
    seen = set()
    out = []

    for row in rows:
        key = (
            row.get("date", ""),
            row.get("author", ""),
            row.get("title", ""),
            row.get("body", ""),
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(row)

    return out


def scrape_reviews(page: Page) -> List[Dict[str, str]]:
    all_rows: List[Dict[str, str]] = []

    found_header = slow_scroll_until_reviews_header(page)
    if not found_header:
        return []

    if not wait_for_reviews_root(page):
        return []

    page_number = 1
    all_rows.extend(scrape_visible_review_page(page, page_number))

    next_n = 2
    while True:
        ok = click_next_page(page, next_n)
        if not ok:
            break
        page.wait_for_timeout(800)
        all_rows.extend(scrape_visible_review_page(page, next_n))
        next_n += 1

    return dedupe_reviews(all_rows)


def scrape_one_product(page: Page, url: str) -> Dict[str, Any]:
    page.goto(url, wait_until="load", timeout=90000)
    page.wait_for_timeout(1500)

    accept_cookies(page)

    product_info = scrape_product_info(page)
    reviews = scrape_reviews(page)

    return {
        "url": url,
        "price": product_info.get("price", ""),
        "review_count": len(reviews),
        "reviews": reviews,
    }


def scrape_mediamarkt_reviews(url: str, *, headless: bool = True) -> Dict[str, Any]:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        page = browser.new_page(viewport={"width": 1400, "height": 1200})

        try:
            return scrape_one_product(page, url)
        finally:
            browser.close()


def main(url: str) -> None:
    import json

    data = scrape_mediamarkt_reviews(url, headless=False)
    print(json.dumps(data, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python reviews_scraper_mediamarkt.py <product_url>")

    main(sys.argv[1])
