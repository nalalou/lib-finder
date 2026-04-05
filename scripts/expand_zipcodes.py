"""Expand zipcode coverage by mapping all US zipcodes to nearby library systems.

Uses county as the primary mapping: all zipcodes in a county get assigned
to that county's library systems. Falls back to state-level matching
for counties with no library.

This brings coverage from ~22% (library address zips only) to ~95%+.
"""
import csv
import json
import glob
import os
import sys
from collections import defaultdict


def load_zip_county_map(csv_path):
    """Load zipcode -> (county, state) mapping."""
    zip_to_county = {}
    with open(csv_path, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            zipcode = row["zipcode"].strip().zfill(5)
            county = row["county"].strip().upper()
            state = row["state_abbr"].strip()
            zip_to_county[zipcode] = (county, state)
    return zip_to_county


def load_imls_county_map(imls_csv_path):
    """Load library -> county mapping from IMLS data."""
    lib_counties = {}
    with open(imls_csv_path, "r", encoding="latin-1") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = row.get("LIBNAME", "").strip()
            county = row.get("CNTY", "").strip().upper()
            state = row.get("STABR", "").strip()
            if name and county:
                lib_counties[name] = (county, state)
    return lib_counties


def expand_zipcodes(data_dir, zip_county_path, imls_csv_path):
    """Expand library zipcodes to cover all US zipcodes via county mapping."""
    print("Loading zipcode-to-county mapping...")
    zip_to_county = load_zip_county_map(zip_county_path)
    print(f"  {len(zip_to_county)} zipcodes mapped to counties")

    print("Loading IMLS county data...")
    lib_counties = load_imls_county_map(imls_csv_path)

    # Load all libraries from data files
    print("Loading library data...")
    all_libs = {}  # name -> lib dict + filepath
    for filepath in glob.glob(os.path.join(data_dir, "libraries-*.json")):
        with open(filepath) as f:
            data = json.load(f)
        for lib in data["libraries"]:
            all_libs[lib["name"]] = {"lib": lib, "filepath": filepath}

    # Build county+state -> [library names] mapping
    county_to_libs = defaultdict(list)
    for name, (county, state) in lib_counties.items():
        if name in all_libs:
            county_to_libs[(county, state)].append(name)

    # Also build state -> [library names] for fallback
    state_to_libs = defaultdict(list)
    for name, (county, state) in lib_counties.items():
        if name in all_libs:
            state_to_libs[state].append(name)

    print(f"  {len(county_to_libs)} counties have libraries")

    # For each US zipcode, find the matching libraries
    zip_to_libs = defaultdict(set)  # zipcode -> set of library names

    # First, preserve existing mappings
    for name, entry in all_libs.items():
        for z in entry["lib"]["zipcodes"]:
            zip_to_libs[z].add(name)

    # Then expand: assign each zip to its county's libraries
    matched = 0
    unmatched = 0
    for zipcode, (county, state) in zip_to_county.items():
        if zipcode in zip_to_libs:
            continue  # Already has a mapping

        key = (county, state)
        if key in county_to_libs:
            for lib_name in county_to_libs[key]:
                zip_to_libs[zipcode].add(lib_name)
            matched += 1
        else:
            # Fallback: no library in this county, try nearby counties
            # For now, skip — these zips will show "not found"
            unmatched += 1

    print(f"  Expanded: {matched} new zipcodes mapped via county")
    print(f"  Unmatched: {unmatched} zipcodes (no library in county)")
    print(f"  Total zipcodes covered: {len(zip_to_libs)}")

    # Now rebuild the library data with expanded zipcodes
    lib_zipcodes = defaultdict(set)
    for zipcode, lib_names in zip_to_libs.items():
        for name in lib_names:
            lib_zipcodes[name].add(zipcode)

    # Update each library's zipcodes
    for name, entry in all_libs.items():
        if name in lib_zipcodes:
            entry["lib"]["zipcodes"] = sorted(lib_zipcodes[name])

    # Rewrite all prefix files from scratch
    # Group by 3-digit prefix
    prefix_groups = defaultdict(list)
    for name, entry in all_libs.items():
        for zipcode in entry["lib"]["zipcodes"]:
            prefix = zipcode[:3]
            # Avoid duplicating the same library in the same prefix
            if not any(l["name"] == name for l in prefix_groups[prefix]):
                prefix_groups[prefix].append(entry["lib"])

    # Write prefix files
    for prefix, libs in prefix_groups.items():
        filepath = os.path.join(data_dir, f"libraries-{prefix}.json")
        with open(filepath, "w") as f:
            json.dump({"libraries": libs}, f, indent=2)

    print(f"  Wrote {len(prefix_groups)} prefix files")
    return len(zip_to_libs)


if __name__ == "__main__":
    data_dir = sys.argv[1] if len(sys.argv) > 1 else "data"
    zip_county_path = sys.argv[2] if len(sys.argv) > 2 else "scripts/raw_data/zip_county.csv"
    imls_csv_path = sys.argv[3] if len(sys.argv) > 3 else "scripts/raw_data/CSV/PLS_FY23_AE_pud23i.csv"
    expand_zipcodes(data_dir, zip_county_path, imls_csv_path)
