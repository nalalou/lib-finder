import json
import os
import tempfile
from scripts.merge_scraper_results import merge_results


def test_merge_updates_form_url():
    libraries_data = {
        "libraries": [
            {"name": "Lib A", "system": "Lib A", "address": "1 Main, City, CA",
             "website": "https://liba.org", "formUrl": None, "formStatus": "unknown",
             "zipcodes": ["90012"]},
            {"name": "Lib B", "system": "Lib B", "address": "2 Oak, Town, CA",
             "website": "https://libb.org", "formUrl": None, "formStatus": "unknown",
             "zipcodes": ["90401"]},
        ]
    }
    scraper_results = [
        {"website": "https://liba.org", "formUrl": "https://liba.org/suggest", "confidence": "high"},
    ]

    with tempfile.TemporaryDirectory() as tmpdir:
        filepath = os.path.join(tmpdir, "libraries-900.json")
        with open(filepath, "w") as f:
            json.dump(libraries_data, f)

        merge_results(tmpdir, scraper_results)

        with open(filepath) as f:
            data = json.load(f)

        lib_a = next(l for l in data["libraries"] if l["name"] == "Lib A")
        assert lib_a["formUrl"] == "https://liba.org/suggest"
        assert lib_a["formStatus"] == "verified"

        lib_b = next(l for l in data["libraries"] if l["name"] == "Lib B")
        assert lib_b["formUrl"] is None
        assert lib_b["formStatus"] == "unknown"


def test_merge_does_not_overwrite_existing_verified():
    libraries_data = {
        "libraries": [
            {"name": "Lib A", "system": "Lib A", "address": "1 Main, City, CA",
             "website": "https://liba.org", "formUrl": "https://liba.org/existing-form",
             "formStatus": "verified", "zipcodes": ["90012"]},
        ]
    }
    scraper_results = [
        {"website": "https://liba.org", "formUrl": "https://liba.org/different", "confidence": "low"},
    ]

    with tempfile.TemporaryDirectory() as tmpdir:
        filepath = os.path.join(tmpdir, "libraries-900.json")
        with open(filepath, "w") as f:
            json.dump(libraries_data, f)

        merge_results(tmpdir, scraper_results)

        with open(filepath) as f:
            data = json.load(f)

        lib_a = data["libraries"][0]
        assert lib_a["formUrl"] == "https://liba.org/existing-form"
