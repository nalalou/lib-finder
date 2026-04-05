import json
import os
import glob


def merge_results(data_dir, scraper_results):
    """Merge scraper results into existing prefix JSON files.

    scraper_results: list of {"website": str, "formUrl": str, "confidence": str}
    Only updates libraries with formStatus "unknown". Does not overwrite "verified".
    Only applies results with confidence "high".
    """
    results_by_site = {}
    for r in scraper_results:
        if r.get("confidence") == "high" and r.get("formUrl"):
            url = r["website"].rstrip("/")
            results_by_site[url] = r["formUrl"]

    for filepath in glob.glob(os.path.join(data_dir, "libraries-*.json")):
        with open(filepath) as f:
            data = json.load(f)

        changed = False
        for lib in data["libraries"]:
            if lib["formStatus"] == "verified":
                continue
            normalized = lib["website"].rstrip("/")
            if normalized in results_by_site:
                lib["formUrl"] = results_by_site[normalized]
                lib["formStatus"] = "verified"
                changed = True

        if changed:
            with open(filepath, "w") as f:
                json.dump(data, f, indent=2)


if __name__ == "__main__":
    import sys
    data_dir = sys.argv[1] if len(sys.argv) > 1 else "data"
    results_path = sys.argv[2] if len(sys.argv) > 2 else "scripts/scraper_results.json"
    with open(results_path) as f:
        results = json.load(f)
    merge_results(data_dir, results)
    print(f"Merged {len(results)} scraper results into {data_dir}/")
