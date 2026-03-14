"""Craigslist scraper using httpx + BeautifulSoup.

Scrapes the search results pages for gigs/jobs in the configured categories
and regions, then fetches individual listing details.
"""

from __future__ import annotations

import asyncio
import hashlib
from datetime import datetime

import httpx
import structlog
from bs4 import BeautifulSoup

from openclaw.models import CraigslistListing, ListingCategory

logger = structlog.get_logger()

# Map our category codes to Craigslist search paths
_CATEGORY_PATHS = {
    "cpg": "/search/cpg",  # computer gigs
    "acc": "/search/acc",  # accounting+finance
    "ofc": "/search/ofc",  # admin/office
}

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


def _listing_id(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()[:16]


async def _fetch_page(client: httpx.AsyncClient, url: str) -> str | None:
    """Fetch a page, returning HTML or None on failure."""
    try:
        resp = await client.get(url, headers=_HEADERS, follow_redirects=True)
        resp.raise_for_status()
        return resp.text
    except httpx.HTTPError as e:
        logger.warning("fetch_failed", url=url, error=str(e))
        return None


def _parse_search_results(html: str, region: str, category: str) -> list[dict]:
    """Parse a Craigslist search results page into raw listing dicts."""
    soup = BeautifulSoup(html, "html.parser")
    results = []

    # Craigslist gallery/list items
    for item in soup.select("li.cl-static-search-result, li.cl-search-result"):
        link = item.select_one("a")
        if not link:
            continue
        href = link.get("href", "")
        title = link.get_text(strip=True)
        if not href or not title:
            continue

        # Ensure absolute URL
        if href.startswith("/"):
            href = f"https://{region}.craigslist.org{href}"

        results.append(
            {
                "url": href,
                "title": title,
                "region": region,
                "category": category,
            }
        )

    return results


def _parse_listing_detail(html: str) -> dict:
    """Extract body text and compensation from a listing detail page."""
    soup = BeautifulSoup(html, "html.parser")
    body_el = soup.select_one("#postingbody")
    body = ""
    if body_el:
        # Remove the "QR Code Link to This Post" boilerplate
        for script in body_el.find_all(["script", "div"]):
            script.decompose()
        body = body_el.get_text(separator="\n", strip=True)

    # Try to find compensation
    comp = ""
    comp_el = soup.select_one("span.compensation")
    if comp_el:
        comp = comp_el.get_text(strip=True)

    # Posted datetime
    time_el = soup.select_one("time.date.timeago")
    posted_at = None
    if time_el and time_el.get("datetime"):
        try:
            posted_at = datetime.fromisoformat(time_el["datetime"].replace("Z", "+00:00"))
        except ValueError:
            pass

    return {"body": body, "compensation": comp, "posted_at": posted_at}


async def scrape_region_category(
    client: httpx.AsyncClient,
    region: str,
    category: str,
    seen_ids: set[str],
) -> list[CraigslistListing]:
    """Scrape one region+category combination, returning new listings."""
    path = _CATEGORY_PATHS.get(category)
    if not path:
        logger.warning("unknown_category", category=category)
        return []

    search_url = f"https://{region}.craigslist.org{path}"
    logger.info("scraping_search", url=search_url)

    html = await _fetch_page(client, search_url)
    if not html:
        return []

    raw_results = _parse_search_results(html, region, category)
    listings: list[CraigslistListing] = []

    for raw in raw_results:
        lid = _listing_id(raw["url"])
        if lid in seen_ids:
            continue
        seen_ids.add(lid)

        # Fetch detail page
        detail_html = await _fetch_page(client, raw["url"])
        detail = _parse_listing_detail(detail_html) if detail_html else {}

        # Small delay to be respectful
        await asyncio.sleep(1.0)

        listings.append(
            CraigslistListing(
                id=lid,
                title=raw["title"],
                url=raw["url"],
                body=detail.get("body", ""),
                region=region,
                category=ListingCategory(category),
                compensation=detail.get("compensation", ""),
                posted_at=detail.get("posted_at"),
            )
        )

    logger.info("scrape_complete", region=region, category=category, new_listings=len(listings))
    return listings


async def scrape_all(
    regions: list[str],
    categories: list[str],
    seen_ids: set[str],
) -> list[CraigslistListing]:
    """Scrape all configured regions and categories."""
    all_listings: list[CraigslistListing] = []

    async with httpx.AsyncClient(timeout=30.0) as client:
        for region in regions:
            for category in categories:
                new = await scrape_region_category(client, region, category, seen_ids)
                all_listings.extend(new)
                # Rate-limit between region/category combos
                await asyncio.sleep(2.0)

    logger.info("full_scrape_complete", total_new=len(all_listings))
    return all_listings
