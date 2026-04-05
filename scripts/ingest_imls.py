import csv
import json
import os
import re

from scripts.generate_ids import generate_id


def normalize_name(name):
    """Normalize a library name for fuzzy matching."""
    name = name.lower().strip()
    # Remove common suffixes/prefixes for matching
    name = re.sub(r'\b(the|of|and|&)\b', '', name)
    # Remove punctuation
    name = re.sub(r'[^a-z0-9\s]', '', name)
    # Collapse whitespace
    name = re.sub(r'\s+', ' ', name).strip()
    return name


def load_wikidata_urls(wikidata_path):
    """Load library website URLs from Wikidata SPARQL export.

    Returns a dict mapping normalized library name -> website URL.
    """
    if not os.path.exists(wikidata_path):
        return {}

    with open(wikidata_path) as f:
        data = json.load(f)

    urls = {}
    for binding in data.get("results", {}).get("bindings", []):
        name = binding.get("libraryLabel", {}).get("value", "")
        website = binding.get("website", {}).get("value", "")
        if name and website:
            key = normalize_name(name)
            if key not in urls:
                urls[key] = website
    return urls


def parse_imls_csv(csv_path, wikidata_urls=None):
    """Parse IMLS Public Libraries Survey CSV into library records.

    Enriches with website URLs from Wikidata when available.
    Libraries without a website URL still get included (linked to homepage search).
    """
    if wikidata_urls is None:
        wikidata_urls = {}

    libraries = []
    with open(csv_path, "r", encoding="latin-1") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = row.get("LIBNAME", "").strip()
            if not name:
                continue

            city = row.get("CITY", "").strip()
            state = row.get("STABR", "").strip()
            zipcode = row.get("ZIP", "").strip()[:5]

            if not zipcode or len(zipcode) < 5:
                continue

            # Try to match website from Wikidata
            normalized = normalize_name(name)
            website = wikidata_urls.get(normalized)

            # Also try with city for disambiguation
            if not website:
                with_city = normalize_name(f"{name} {city}")
                website = wikidata_urls.get(with_city)

            # Build a search URL as fallback so users can still find the library
            if not website:
                search_query = f"{name} {city} {state} library".replace(" ", "+")
                website = f"https://www.google.com/search?q={search_query}"
                has_real_website = False
            else:
                if not website.startswith("http"):
                    website = "https://" + website
                has_real_website = True

            libraries.append({
                "name": name,
                "system": name,
                "address": f"{row.get('ADDRESS', '').strip()}, {city}, {state}",
                "website": website,
                "formUrl": None,
                "formStatus": "unknown",
                "zipcodes": [zipcode],
                "hasRealWebsite": has_real_website,
            })
    return libraries


def group_by_prefix(libraries):
    """Group libraries by 3-digit zipcode prefix. A library may appear in multiple groups."""
    groups = {}
    for lib in libraries:
        for zipcode in lib["zipcodes"]:
            prefix = zipcode[:3]
            if prefix not in groups:
                groups[prefix] = []
            if not any(existing["name"] == lib["name"] and existing["website"] == lib["website"]
                       for existing in groups[prefix]):
                groups[prefix].append(lib)
    return groups


def write_prefix_files(libraries, output_dir):
    """Write 3-digit prefix JSON files to output_dir."""
    os.makedirs(output_dir, exist_ok=True)
    groups = group_by_prefix(libraries)
    seen = {}
    for prefix, libs in sorted(groups.items()):
        clean_libs = []
        for lib in libs:
            clean = {k: v for k, v in lib.items() if k != "hasRealWebsite"}
            base_id = generate_id(clean["name"], clean["address"])
            final_id = base_id
            counter = 2
            while final_id in seen:
                final_id = f"{base_id}-{counter}"
                counter += 1
            seen[final_id] = True
            clean["id"] = final_id
            clean_libs.append(clean)
        filepath = os.path.join(output_dir, f"libraries-{prefix}.json")
        with open(filepath, "w") as f:
            json.dump({"libraries": clean_libs}, f, indent=2)
    return list(groups.keys())


if __name__ == "__main__":
    import sys
    csv_path = sys.argv[1] if len(sys.argv) > 1 else "scripts/raw_data/CSV/PLS_FY23_AE_pud23i.csv"
    wikidata_path = sys.argv[2] if len(sys.argv) > 2 else "scripts/raw_data/wikidata_libraries.json"
    output_dir = sys.argv[3] if len(sys.argv) > 3 else "data"

    print(f"Loading Wikidata URLs from {wikidata_path}...")
    wikidata_urls = load_wikidata_urls(wikidata_path)
    print(f"  Loaded {len(wikidata_urls)} library URLs from Wikidata")

    print(f"Parsing IMLS data from {csv_path}...")
    libraries = parse_imls_csv(csv_path, wikidata_urls)

    matched = sum(1 for lib in libraries if not lib["website"].startswith("https://www.google.com"))
    print(f"  Parsed {len(libraries)} libraries, {matched} matched with Wikidata URLs ({100*matched/len(libraries):.1f}%)")

    prefixes = write_prefix_files(libraries, output_dir)
    print(f"  Wrote {len(prefixes)} prefix files to {output_dir}/")
