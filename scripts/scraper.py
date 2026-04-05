import asyncio
import json
import os
import re
import sys
from playwright.async_api import async_playwright

# Patterns that indicate a "request a purchase" or "suggest a title" link
LINK_PATTERNS = [
    re.compile(r"suggest.*purchase", re.IGNORECASE),
    re.compile(r"request.*purchase", re.IGNORECASE),
    re.compile(r"purchase.*request", re.IGNORECASE),
    re.compile(r"purchase.*suggest", re.IGNORECASE),
    re.compile(r"recommend.*book", re.IGNORECASE),
    re.compile(r"suggest.*title", re.IGNORECASE),
    re.compile(r"request.*title", re.IGNORECASE),
    re.compile(r"suggest.*book", re.IGNORECASE),
    re.compile(r"request.*book", re.IGNORECASE),
    re.compile(r"suggest.*material", re.IGNORECASE),
    re.compile(r"request.*material", re.IGNORECASE),
    re.compile(r"patron.*request", re.IGNORECASE),
    re.compile(r"interlibrary.*loan", re.IGNORECASE),
    re.compile(r"suggest.*item", re.IGNORECASE),
    re.compile(r"request.*item", re.IGNORECASE),
]

# Patterns in URLs that suggest a purchase request form
URL_PATTERNS = [
    re.compile(r"suggest", re.IGNORECASE),
    re.compile(r"purchase", re.IGNORECASE),
    re.compile(r"request", re.IGNORECASE),
    re.compile(r"recommend", re.IGNORECASE),
]

# Indicators that a page is a form (has input fields, textareas, selects)
FORM_SELECTORS = ["form", "input[type='text']", "textarea", "select", "iframe"]


async def find_purchase_form(page, website_url):
    """Visit a library website and attempt to find the purchase request form URL.

    Returns: {"website": str, "formUrl": str|None, "confidence": str, "note": str}
    """
    result = {"website": website_url, "formUrl": None, "confidence": "none", "note": ""}

    try:
        response = await page.goto(website_url, wait_until="domcontentloaded", timeout=15000)
        if not response or response.status >= 400:
            result["note"] = f"HTTP {response.status if response else 'no response'}"
            return result
    except Exception as e:
        result["note"] = f"Failed to load: {str(e)[:100]}"
        return result

    # Search for matching links on the page
    links = await page.query_selector_all("a")
    candidates = []

    for link in links:
        try:
            text = (await link.inner_text()).strip()
            href = await link.get_attribute("href")
            if not href or href.startswith("#") or href.startswith("mailto:") or href.startswith("tel:"):
                continue

            text_match = any(p.search(text) for p in LINK_PATTERNS)
            url_match = any(p.search(href) for p in URL_PATTERNS)

            if text_match or url_match:
                candidates.append({"text": text, "href": href, "text_match": text_match, "url_match": url_match})
        except Exception:
            continue

    if not candidates:
        result["note"] = "No matching links found on homepage"
        return result

    # Sort: text matches first (more reliable), then URL matches
    candidates.sort(key=lambda c: (not c["text_match"], not c["url_match"]))
    best = candidates[0]

    # Follow the best candidate link
    try:
        await page.click(f"a[href='{best['href']}']", timeout=5000)
        await page.wait_for_load_state("domcontentloaded", timeout=10000)
    except Exception:
        try:
            # Try direct navigation if click fails
            full_url = best["href"]
            if not full_url.startswith("http"):
                full_url = website_url.rstrip("/") + "/" + full_url.lstrip("/")
            await page.goto(full_url, wait_until="domcontentloaded", timeout=15000)
        except Exception as e:
            result["note"] = f"Could not follow link: {str(e)[:100]}"
            return result

    # Check if the destination page has a form
    form_url = page.url
    has_form = False
    for selector in FORM_SELECTORS:
        try:
            element = await page.query_selector(selector)
            if element:
                has_form = True
                break
        except Exception:
            continue

    result["formUrl"] = form_url
    if has_form and best["text_match"]:
        result["confidence"] = "high"
        result["note"] = f"Found form via link text: '{best['text']}'"
    elif has_form:
        result["confidence"] = "medium"
        result["note"] = f"Found form via URL pattern: '{best['href']}'"
    else:
        result["confidence"] = "low"
        result["note"] = f"Link matched but no form detected: '{best['text']}'"

    return result


async def scrape_libraries(libraries, output_path, screenshot_dir=None, start_index=0, batch_size=50):
    """Scrape a batch of libraries for purchase request form URLs.

    Args:
        libraries: list of library dicts with "website" key
        output_path: where to write results JSON
        screenshot_dir: optional dir to save screenshots for review
        start_index: index to start from (for resuming)
        batch_size: how many to process in this run
    """
    if screenshot_dir:
        os.makedirs(screenshot_dir, exist_ok=True)

    # Load existing results if resuming
    results = []
    if os.path.exists(output_path):
        with open(output_path) as f:
            results = json.load(f)
    seen_websites = {r["website"] for r in results}

    batch = libraries[start_index:start_index + batch_size]
    print(f"Scraping {len(batch)} libraries (index {start_index}-{start_index + len(batch) - 1})...")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()

        for i, lib in enumerate(batch):
            website = lib["website"]
            if website in seen_websites:
                continue

            print(f"  [{start_index + i + 1}] {lib['name']}: {website}")
            page = await context.new_page()

            try:
                result = await find_purchase_form(page, website)
                result["libraryName"] = lib["name"]
                results.append(result)

                status = "FOUND" if result["formUrl"] else "NOT FOUND"
                print(f"    {status} ({result['confidence']}): {result['note']}")

                if screenshot_dir and result["formUrl"]:
                    safe_name = re.sub(r"[^a-zA-Z0-9]", "_", lib["name"])[:50]
                    await page.screenshot(
                        path=os.path.join(screenshot_dir, f"{safe_name}.png"),
                        full_page=False,
                    )
            except Exception as e:
                results.append({
                    "website": website,
                    "libraryName": lib["name"],
                    "formUrl": None,
                    "confidence": "none",
                    "note": f"Error: {str(e)[:100]}",
                })
                print(f"    ERROR: {str(e)[:100]}")
            finally:
                await page.close()

            # Save after each library so we can resume
            with open(output_path, "w") as f:
                json.dump(results, f, indent=2)

        await browser.close()

    found = sum(1 for r in results if r["formUrl"] and r["confidence"] == "high")
    print(f"\nDone. {found}/{len(results)} libraries have high-confidence form URLs.")
    return results


if __name__ == "__main__":
    # Usage: python scripts/scraper.py [data_dir] [output_path] [start_index] [batch_size]
    data_dir = sys.argv[1] if len(sys.argv) > 1 else "data"
    output_path = sys.argv[2] if len(sys.argv) > 2 else "scripts/scraper_results.json"
    start_index = int(sys.argv[3]) if len(sys.argv) > 3 else 0
    batch_size = int(sys.argv[4]) if len(sys.argv) > 4 else 50

    # Load all libraries from prefix files
    all_libraries = []
    for filepath in sorted(
        f for f in os.listdir(data_dir) if f.startswith("libraries-") and f.endswith(".json")
    ):
        with open(os.path.join(data_dir, filepath)) as f:
            data = json.load(f)
            all_libraries.extend(data["libraries"])

    # Deduplicate by website
    seen = set()
    unique = []
    for lib in all_libraries:
        if lib["website"] not in seen:
            seen.add(lib["website"])
            unique.append(lib)

    print(f"Found {len(unique)} unique library websites.")
    asyncio.run(scrape_libraries(unique, output_path, screenshot_dir="scripts/screenshots",
                                  start_index=start_index, batch_size=batch_size))
