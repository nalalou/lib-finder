import json
import os
import tempfile
import pytest
from scripts.generate_ids import slugify, extract_state, generate_id, add_ids_to_file


def test_slugify_basic():
    assert slugify("HAMPTON PUBLIC LIBRARY") == "hampton-public-library"


def test_slugify_strips_punctuation():
    assert slugify("ST. MARY'S LIBRARY") == "st-marys-library"


def test_slugify_collapses_whitespace():
    assert slugify("THE   BIG   LIBRARY") == "the-big-library"


def test_extract_state_from_address():
    assert extract_state("4 S FEDERAL ST, HAMPTON, IA") == "ia"


def test_extract_state_two_word_city():
    assert extract_state("476 FIFTH AVENUE, NEW YORK, NY") == "ny"


def test_extract_state_missing_returns_none():
    assert extract_state("NO COMMA HERE") is None


def test_generate_id():
    assert generate_id("HAMPTON PUBLIC LIBRARY", "4 S FEDERAL ST, HAMPTON, IA") == "hampton-public-library-ia"


def test_generate_id_no_state():
    assert generate_id("SOME LIBRARY", "NO COMMA HERE") == "some-library"


def test_add_ids_to_file_adds_ids():
    data = {
        "libraries": [
            {
                "name": "LIB A",
                "system": "LIB A",
                "address": "1 MAIN ST, CITY, CA",
                "website": "https://a.org",
                "formUrl": None,
                "formStatus": "unknown",
                "zipcodes": ["90012"]
            },
            {
                "name": "LIB B",
                "system": "LIB B",
                "address": "2 OAK AVE, TOWN, NY",
                "website": "https://b.org",
                "formUrl": None,
                "formStatus": "unknown",
                "zipcodes": ["10018"]
            }
        ]
    }
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(data, f)
        f.flush()
        seen = {}
        add_ids_to_file(f.name, seen)

    with open(f.name) as fh:
        result = json.load(fh)

    assert result["libraries"][0]["id"] == "lib-a-ca"
    assert result["libraries"][1]["id"] == "lib-b-ny"
    os.unlink(f.name)


def test_add_ids_to_file_handles_collisions():
    data = {
        "libraries": [
            {
                "name": "MAIN LIBRARY",
                "system": "MAIN LIBRARY",
                "address": "1 ST, CITY, CA",
                "website": "https://a.org",
                "formUrl": None,
                "formStatus": "unknown",
                "zipcodes": ["90012"]
            },
            {
                "name": "MAIN LIBRARY",
                "system": "MAIN LIBRARY",
                "address": "2 ST, TOWN, CA",
                "website": "https://b.org",
                "formUrl": None,
                "formStatus": "unknown",
                "zipcodes": ["90013"]
            }
        ]
    }
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(data, f)
        f.flush()
        seen = {}
        add_ids_to_file(f.name, seen)

    with open(f.name) as fh:
        result = json.load(fh)

    assert result["libraries"][0]["id"] == "main-library-ca"
    assert result["libraries"][1]["id"] == "main-library-ca-2"
    os.unlink(f.name)


def test_add_ids_to_file_handles_cross_file_collisions():
    """IDs must be globally unique across all prefix files."""
    data1 = {
        "libraries": [
            {"name": "MAIN LIBRARY", "system": "MAIN LIBRARY",
             "address": "1 ST, CITY, CA", "website": "https://a.org",
             "formUrl": None, "formStatus": "unknown", "zipcodes": ["90012"]}
        ]
    }
    data2 = {
        "libraries": [
            {"name": "MAIN LIBRARY", "system": "MAIN LIBRARY",
             "address": "2 ST, TOWN, CA", "website": "https://b.org",
             "formUrl": None, "formStatus": "unknown", "zipcodes": ["10018"]}
        ]
    }
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f1, \
         tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f2:
        json.dump(data1, f1)
        f1.flush()
        json.dump(data2, f2)
        f2.flush()

        seen = {}
        add_ids_to_file(f1.name, seen)
        add_ids_to_file(f2.name, seen)

    with open(f1.name) as fh:
        r1 = json.load(fh)
    with open(f2.name) as fh:
        r2 = json.load(fh)

    assert r1["libraries"][0]["id"] == "main-library-ca"
    assert r2["libraries"][0]["id"] == "main-library-ca-2"
    os.unlink(f1.name)
    os.unlink(f2.name)
