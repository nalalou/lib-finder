"""Discover library website URLs using web search.

For libraries without a known website, searches Google for the library
and extracts the most likely official website URL.
Run before the purchase form scraper.
"""
import asyncio
import json
import glob
import os
import re
import sys
from playwright.async_api import async_playwright


# Domains that are definitely NOT the library's own website
SKIP_DOMAINS = {
    "google.com", "yelp.com", "facebook.com", "twitter.com", "instagram.com",
    "linkedin.com", "wikipedia.org", "wikidata.org", "tripadvisor.com",
    "yellowpages.com", "mapquest.com", "bbb.org", "indeed.com",
    "glassdoor.com", "pinterest.com", "tiktok.com", "youtube.com",
}

# Domains that strongly suggest a library website
LIBRARY_DOMAIN_HINTS = [".gov", ".org", ".us", ".edu", "library", "lib."]


def is_likely_library_site(url):
    """Check if a URL is likely an official library website."""
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        hostname = parsed.hostname.lower() if parsed.hostname else ""

        # Skip known non-library domains
        for skip in SKIP_DOMAINS:
            if hostname.endswith(skip):
                return False

        # Prefer library-ish domains
        for hint in LIBRARY_DOMAIN_HINTS:
            if hint in hostname:
                return True

        # Accept .com if it has "library" in the path
        if "library" in url.lower() or "lib" in hostname:
            return True

        return False
    except Exception:
        return False


async def discover_website(page, library_name, city, state):
    """Search for a library's official website.

    Returns the URL if found, None otherwise.
    """
    query = f"{library_name} {city} {state} official website"
    search_url = f"https://www.google.com/search?q={query.replace(' ', '+')}"

    try:
        await page.goto(search_url, wait_until="domcontentloaded", timeout=15000)
        await page.wait_for_timeout(2000)  # Let results load

        # Get all search result links
        links = await page.query_selector_all("a[href]")
        for link in links:
            href = await link.get_attribute("href")
            if not href or not href.startswith("http"):
                continue
            if is_likely_library_site(href):
                # Verify it's not a search engine redirect
                if "google.com" not in href:
                    return href

        return None
    except Exception as e:
        print(f"    Search error: {str(e)[:80]}")
        return None


async def discover_for_data_dir(data_dir, start_index=0, batch_size=50):
    """Discover websites for libraries that only have Google search fallbacks."""
    files = sorted(glob.glob(os.path.join(data_dir, "libraries-*.json")))

    # Collect all libraries needing discovery
    needs_discovery = []
    for filepath in files:
        with open(filepath) as f:
            data = json.load(f)
        for lib in data["libraries"]:
            if lib["website"].startswith("https://www.google.com/search"):
                needs_discovery.append({"lib": lib, "filepath": filepath})

    print(f"Found {len(needs_discovery)} libraries needing website discovery")

    batch = needs_discovery[start_index:start_index + batch_size]
    if not batch:
        print("Nothing to do in this batch.")
        return

    print(f"Processing batch: index {start_index} to {start_index + len(batch) - 1}")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        )

        found = 0
        files_changed = set()

        for i, entry in enumerate(batch):
            lib = entry["lib"]
            filepath = entry["filepath"]

            parts = lib["address"].split(",")
            city = parts[-2].strip() if len(parts) >= 2 else ""
            state = parts[-1].strip() if len(parts) >= 1 else ""

            print(f"  [{start_index + i + 1}] {lib['name']} ({city}, {state})")

            page = await context.new_page()
            url = await discover_website(page, lib["name"], city, state)
            await page.close()

            if url:
                lib["website"] = url
                files_changed.add(filepath)
                found += 1
                print(f"    FOUND: {url}")
            else:
                print(f"    NOT FOUND")

            # Rate limit to avoid Google blocks
            await asyncio.sleep(2)

        await browser.close()

    # Write back changed files
    for filepath in files_changed:
        with open(filepath) as f:
            data = json.load(f)
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)

    print(f"\nDiscovered {found}/{len(batch)} library websites")


if __name__ == "__main__":
    data_dir = sys.argv[1] if len(sys.argv) > 1 else "data"
    start_index = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    batch_size = int(sys.argv[3]) if len(sys.argv) > 3 else 50
    asyncio.run(discover_for_data_dir(data_dir, start_index, batch_size))
