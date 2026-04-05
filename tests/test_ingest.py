import json
import os
import tempfile
import pytest
from scripts.ingest_imls import parse_imls_csv, write_prefix_files

SAMPLE_CSV = """STABR,LIBNAME,ADDRESS,CITY,ZIP,GEOCODE,WEBSITE
CA,Los Angeles Public Library,630 W 5th St,Los Angeles,90071,0637000,https://lapl.org
CA,Santa Monica Public Library,601 Santa Monica Blvd,Santa Monica,90401,0670000,https://smpl.org
NY,New York Public Library,476 5th Ave,New York,10018,3651000,https://nypl.org
NY,Brooklyn Public Library,10 Grand Army Plaza,Brooklyn,11238,3651000,https://bklynlibrary.org
"""


def test_parse_imls_csv_returns_library_list():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write(SAMPLE_CSV)
        f.flush()
        libraries = parse_imls_csv(f.name)

    assert len(libraries) == 4
    assert libraries[0]["name"] == "Los Angeles Public Library"
    assert libraries[0]["website"] == "https://lapl.org"
    assert libraries[0]["zipcodes"] == ["90071"]
    assert libraries[0]["address"] == "630 W 5th St, Los Angeles, CA"
    assert libraries[0]["formUrl"] is None
    assert libraries[0]["formStatus"] == "unknown"
    os.unlink(f.name)


def test_parse_imls_csv_skips_rows_without_website():
    csv_content = """STABR,LIBNAME,ADDRESS,CITY,ZIP,GEOCODE,WEBSITE
CA,No Website Library,123 Main St,Nowhere,90000,0000000,
CA,Has Website Library,456 Oak Ave,Somewhere,90001,0000001,https://example.org
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write(csv_content)
        f.flush()
        libraries = parse_imls_csv(f.name)

    assert len(libraries) == 1
    assert libraries[0]["name"] == "Has Website Library"
    os.unlink(f.name)


def test_write_prefix_files_creates_correct_files():
    libraries = [
        {"name": "Lib A", "system": "Lib A", "address": "1 Main St, City, CA",
         "website": "https://a.org", "formUrl": None, "formStatus": "unknown",
         "zipcodes": ["90012"]},
        {"name": "Lib B", "system": "Lib B", "address": "2 Oak Ave, Town, NY",
         "website": "https://b.org", "formUrl": None, "formStatus": "unknown",
         "zipcodes": ["10018"]},
    ]
    with tempfile.TemporaryDirectory() as tmpdir:
        prefixes = write_prefix_files(libraries, tmpdir)
        assert sorted(prefixes) == ["100", "900"]

        with open(os.path.join(tmpdir, "libraries-900.json")) as f:
            data = json.load(f)
        assert len(data["libraries"]) == 1
        assert data["libraries"][0]["name"] == "Lib A"

        with open(os.path.join(tmpdir, "libraries-100.json")) as f:
            data = json.load(f)
        assert len(data["libraries"]) == 1
        assert data["libraries"][0]["name"] == "Lib B"
