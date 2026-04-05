"""Discover library website URLs using DuckDuckGo Lite.

For libraries without a known website, searches DuckDuckGo for the library
and extracts the most likely official website URL.
Run before the purchase form scraper.

Safe for parallel execution: each batch writes to its own output file.
Merge results into data/ after all batches complete.
"""
import asyncio
import json
import glob
import os
import re
import sys
from urllib.parse import urlparse, parse_qs, unquote
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


def extract_ddg_url(redirect_href):
    """Extract the actual URL from a DuckDuckGo Lite redirect link.

    DDG Lite links look like: //duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.org&rut=...
    """
    try:
        if "uddg=" in redirect_href:
            parsed = parse_qs(urlparse(redirect_href).query)
            urls = parsed.get("uddg", [])
            if urls:
                return unquote(urls[0])
    except Exception:
        pass
    return None


async def discover_website(page, library_name, city, state):
    """Search for a library's official website using DuckDuckGo Lite.

    Returns the URL if found, None otherwise.
    """
    query = f"{library_name} {city} {state} library"
    search_url = f"https://lite.duckduckgo.com/lite/?q={query.replace(' ', '+')}"

    try:
        await page.goto(search_url, wait_until="domcontentloaded", timeout=15000)

        # DDG Lite uses a.result-link for search results
        result_links = await page.query_selector_all("a.result-link")

        for link in result_links:
            redirect_href = await link.get_attribute("href")
            if not redirect_href:
                continue

            # Extract actual URL from DDG redirect
            actual_url = extract_ddg_url(redirect_href)
            if not actual_url:
                continue

            if is_likely_library_site(actual_url):
                return actual_url

        return None
    except Exception as e:
        print(f"    Search error: {str(e)[:80]}")
        return None


def collect_libraries_needing_discovery(data_dir):
    """Collect all libraries that need website discovery."""
    files = sorted(glob.glob(os.path.join(data_dir, "libraries-*.json")))
    needs_discovery = []
    for filepath in files:
        with open(filepath) as f:
            data = json.load(f)
        for lib in data["libraries"]:
            if lib["website"].startswith("https://www.google.com/search"):
                needs_discovery.append({
                    "name": lib["name"],
                    "address": lib["address"],
                    "filepath": filepath,
                })
    return needs_discovery


async def discover_for_batch(data_dir, output_path, start_index=0, batch_size=50):
    """Discover websites for a batch of libraries.

    Writes results to a separate JSON file (safe for parallel execution).
    Does NOT modify data/ files directly — use merge step after.
    """
    needs_discovery = collect_libraries_needing_discovery(data_dir)
    print(f"Total libraries needing discovery: {len(needs_discovery)}")

    batch = needs_discovery[start_index:start_index + batch_size]
    if not batch:
        print("Nothing to do in this batch.")
        return

    print(f"Processing batch: index {start_index} to {start_index + len(batch) - 1}")
    print(f"Results will be written to: {output_path}")

    # Load existing results if resuming
    results = []
    if os.path.exists(output_path):
        with open(output_path) as f:
            results = json.load(f)
    seen = {r["name"] for r in results}

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()

        found = 0

        for i, entry in enumerate(batch):
            if entry["name"] in seen:
                continue

            parts = entry["address"].split(",")
            city = parts[-2].strip() if len(parts) >= 2 else ""
            state = parts[-1].strip() if len(parts) >= 1 else ""

            print(f"  [{start_index + i + 1}] {entry['name']} ({city}, {state})")

            page = await context.new_page()
            url = await discover_website(page, entry["name"], city, state)
            await page.close()

            result = {"name": entry["name"], "website": url, "address": entry["address"]}
            results.append(result)

            if url:
                found += 1
                print(f"    FOUND: {url}")
            else:
                print(f"    NOT FOUND")

            # Save after each so we can resume
            with open(output_path, "w") as f:
                json.dump(results, f, indent=2)

            # Rate limit to be respectful to DuckDuckGo
            await asyncio.sleep(1)

        await browser.close()

    print(f"\nDiscovered {found}/{len(batch)} library websites")
    print(f"Results saved to {output_path}")


def merge_discoveries(data_dir, results_dir="scripts/discovery_results"):
    """Merge all discovery result files back into data/ JSON files."""
    # Load all results from all batch files
    all_results = {}
    for filepath in glob.glob(os.path.join(results_dir, "discovery_batch_*.json")):
        with open(filepath) as f:
            for r in json.load(f):
                if r.get("website"):
                    all_results[r["name"]] = r["website"]

    print(f"Loaded {len(all_results)} discovered URLs from {results_dir}/")

    # Apply to data files
    updated = 0
    for filepath in glob.glob(os.path.join(data_dir, "libraries-*.json")):
        with open(filepath) as f:
            data = json.load(f)

        changed = False
        for lib in data["libraries"]:
            if lib["website"].startswith("https://www.google.com/search"):
                if lib["name"] in all_results:
                    lib["website"] = all_results[lib["name"]]
                    changed = True
                    updated += 1

        if changed:
            with open(filepath, "w") as f:
                json.dump(data, f, indent=2)

    print(f"Updated {updated} libraries in {data_dir}/")
    return updated


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Discover library websites via DuckDuckGo")
    parser.add_argument("--data-dir", default="data", help="Path to data/ directory")
    parser.add_argument("--batch-id", type=int, default=0, help="Batch ID (for parallel runs)")
    parser.add_argument("--start", type=int, default=0, help="Start index")
    parser.add_argument("--size", type=int, default=50, help="Batch size")
    parser.add_argument("--merge", action="store_true", help="Merge all batch results into data/")
    parser.add_argument("--results-dir", default="scripts/discovery_results", help="Dir for batch results")
    args = parser.parse_args()

    if args.merge:
        merge_discoveries(args.data_dir, args.results_dir)
    else:
        os.makedirs(args.results_dir, exist_ok=True)
        output_path = os.path.join(args.results_dir, f"discovery_batch_{args.batch_id}.json")
        asyncio.run(discover_for_batch(args.data_dir, output_path, args.start, args.size))
