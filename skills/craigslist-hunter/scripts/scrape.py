#!/usr/bin/env python3
"""Craigslist scraper — fetches listings and outputs JSON lines.

Usage:
    python3 scrape.py --regions "newyork,sfbay" --categories "cpg,acc,ofc"
    python3 scrape.py --regions "boston" --categories "cpg" --output /tmp/cl_listings.json
"""

import argparse
import hashlib
import json
import sys
import time
from urllib.request import Request, urlopen
from urllib.error import URLError
from html.parser import HTMLParser


# --- Simple HTML parser (no external dependencies) ---

class SearchResultParser(HTMLParser):
    """Parse Craigslist search result pages."""

    def __init__(self):
        super().__init__()
        self.results = []
        self._in_link = False
        self._current = None

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        cls = attrs_dict.get("class", "")

        if tag == "li" and ("cl-static-search-result" in cls or "cl-search-result" in cls):
            self._current = {}

        if tag == "a" and self._current is not None:
            href = attrs_dict.get("href", "")
            if href and ("/d/" in href or href.startswith("http")):
                self._current["url"] = href
                self._in_link = True
                self._current["title"] = ""

    def handle_data(self, data):
        if self._in_link and "title" in self._current:
            self._current["title"] += data.strip()

    def handle_endtag(self, tag):
        if tag == "a" and self._in_link:
            self._in_link = False
            if self._current.get("url") and self._current.get("title"):
                self.results.append(dict(self._current))
            self._current = None


class DetailParser(HTMLParser):
    """Parse a Craigslist listing detail page."""

    def __init__(self):
        super().__init__()
        self.body = ""
        self.compensation = ""
        self._in_body = False
        self._in_comp = False
        self._depth = 0

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        el_id = attrs_dict.get("id", "")
        cls = attrs_dict.get("class", "")

        if el_id == "postingbody":
            self._in_body = True
            self._depth = 0

        if self._in_body and tag in ("div", "script"):
            self._depth += 1

        if "compensation" in cls:
            self._in_comp = True

    def handle_data(self, data):
        if self._in_body and self._depth == 0:
            text = data.strip()
            if text and text != "QR Code Link to This Post":
                self.body += text + "\n"

        if self._in_comp:
            self.compensation += data.strip()

    def handle_endtag(self, tag):
        if self._in_body and tag in ("div", "script"):
            self._depth -= 1

        if tag == "section" and self._in_body:
            self._in_body = False

        if self._in_comp and tag == "span":
            self._in_comp = False


# --- Fetching ---

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

CATEGORY_PATHS = {
    "cpg": "/search/cpg",
    "acc": "/search/acc",
    "ofc": "/search/ofc",
}


def fetch(url: str) -> str | None:
    req = Request(url, headers=HEADERS)
    try:
        with urlopen(req, timeout=20) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except (URLError, TimeoutError, OSError) as e:
        print(f"WARN: Failed to fetch {url}: {e}", file=sys.stderr)
        return None


def listing_id(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()[:16]


def scrape_search(region: str, category: str) -> list[dict]:
    path = CATEGORY_PATHS.get(category)
    if not path:
        print(f"WARN: Unknown category '{category}'", file=sys.stderr)
        return []

    url = f"https://{region}.craigslist.org{path}"
    print(f"Scraping {url} ...", file=sys.stderr)

    html = fetch(url)
    if not html:
        return []

    parser = SearchResultParser()
    parser.feed(html)

    results = []
    for item in parser.results:
        href = item["url"]
        if href.startswith("/"):
            href = f"https://{region}.craigslist.org{href}"

        results.append({
            "id": listing_id(href),
            "title": item["title"],
            "url": href,
            "region": region,
            "category": category,
        })

    return results


def scrape_detail(url: str) -> dict:
    html = fetch(url)
    if not html:
        return {"body": "", "compensation": ""}

    parser = DetailParser()
    parser.feed(html)
    return {
        "body": parser.body.strip(),
        "compensation": parser.compensation.strip(),
    }


def main():
    ap = argparse.ArgumentParser(description="Scrape Craigslist listings")
    ap.add_argument("--regions", default="newyork,sfbay,losangeles,chicago",
                     help="Comma-separated Craigslist subdomains")
    ap.add_argument("--categories", default="cpg,acc,ofc",
                     help="Comma-separated category codes: cpg, acc, ofc")
    ap.add_argument("--output", default="",
                     help="Output file path (default: stdout)")
    ap.add_argument("--no-details", action="store_true",
                     help="Skip fetching individual listing details (faster)")
    args = ap.parse_args()

    regions = [r.strip() for r in args.regions.split(",") if r.strip()]
    categories = [c.strip() for c in args.categories.split(",") if c.strip()]

    all_listings = []
    seen = set()

    for region in regions:
        for category in categories:
            results = scrape_search(region, category)
            for item in results:
                if item["id"] in seen:
                    continue
                seen.add(item["id"])

                if not args.no_details:
                    detail = scrape_detail(item["url"])
                    item["body"] = detail["body"]
                    item["compensation"] = detail["compensation"]
                    time.sleep(1)  # Be respectful
                else:
                    item["body"] = ""
                    item["compensation"] = ""

                all_listings.append(item)

            time.sleep(2)  # Pause between region/category combos

    print(f"Found {len(all_listings)} listings", file=sys.stderr)

    output = json.dumps(all_listings, indent=2)
    if args.output:
        with open(args.output, "w") as f:
            f.write(output)
        print(f"Saved to {args.output}", file=sys.stderr)
    else:
        print(output)


if __name__ == "__main__":
    main()
