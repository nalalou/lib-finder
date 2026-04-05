"""Expand zipcode coverage by mapping all US zipcodes to nearby library systems.

Uses geographic distance: each zipcode gets assigned to the nearest 1-3
libraries in its county (by lat/lng). Falls back to nearest in state
for counties with no library.
"""
import csv
import json
import glob
import math
import os
import sys
from collections import defaultdict


def haversine(lat1, lng1, lat2, lng2):
    """Distance in miles between two lat/lng points."""
    R = 3959  # Earth radius in miles
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng/2)**2
    return R * 2 * math.asin(math.sqrt(a))


def load_zip_coords(coords_path):
    """Load zipcode -> (lat, lng) mapping."""
    coords = {}
    with open(coords_path, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            zipcode = row["ZIP"].strip().zfill(5)
            try:
                lat = float(row["LAT"])
                lng = float(row["LNG"])
                coords[zipcode] = (lat, lng)
            except (ValueError, KeyError):
                continue
    return coords


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


def load_imls_libraries(imls_csv_path):
    """Load library name, county, state, lat, lng from IMLS data."""
    libraries = []
    with open(imls_csv_path, "r", encoding="latin-1") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = row.get("LIBNAME", "").strip()
            county = row.get("CNTY", "").strip().upper()
            state = row.get("STABR", "").strip()
            try:
                lat = float(row.get("LATITUDE", 0))
                lng = float(row.get("LONGITUD", 0))
            except ValueError:
                lat, lng = 0, 0
            if name and lat != 0 and lng != 0:
                libraries.append({
                    "name": name,
                    "county": county,
                    "state": state,
                    "lat": lat,
                    "lng": lng,
                })
    return libraries


MAX_LIBS_PER_ZIP = 3
MAX_DISTANCE_MILES = 10


def expand_zipcodes(data_dir, zip_county_path, zip_coords_path, imls_csv_path):
    """Expand library zipcodes using geographic proximity."""
    print("Loading data...")
    zip_to_county = load_zip_county_map(zip_county_path)
    zip_coords = load_zip_coords(zip_coords_path)
    imls_libs = load_imls_libraries(imls_csv_path)

    print(f"  {len(zip_to_county)} zipcodes with counties")
    print(f"  {len(zip_coords)} zipcodes with coordinates")
    print(f"  {len(imls_libs)} IMLS libraries with coordinates")

    # Load current library data
    all_libs = {}
    for filepath in glob.glob(os.path.join(data_dir, "libraries-*.json")):
        with open(filepath) as f:
            data = json.load(f)
        for lib in data["libraries"]:
            if lib["name"] not in all_libs:
                all_libs[lib["name"]] = lib

    # Build county+state -> [imls library entries] for efficient lookup
    county_libs = defaultdict(list)
    state_libs = defaultdict(list)
    for ilib in imls_libs:
        if ilib["name"] in all_libs:
            county_libs[(ilib["county"], ilib["state"])].append(ilib)
            state_libs[ilib["state"]].append(ilib)

    # For each zipcode, find nearest libraries
    zip_to_libs = defaultdict(set)

    # Preserve original library-address mappings (1:1 — only the library at that address)
    lib_home_zips = {}  # zip -> name of library whose address is at that zip
    for name, lib in all_libs.items():
        original_zip = lib["zipcodes"][0] if lib["zipcodes"] else None
        if original_zip:
            zip_to_libs[original_zip].add(name)
            lib_home_zips.setdefault(original_zip, set()).add(name)

    expanded = 0
    no_coords = 0
    no_match = 0

    all_zips = set(zip_to_county.keys()) | set(zip_coords.keys())

    for zipcode in all_zips:
        if zipcode in zip_to_libs:
            continue

        if zipcode not in zip_coords:
            no_coords += 1
            continue

        zlat, zlng = zip_coords[zipcode]
        county_state = zip_to_county.get(zipcode)

        # Get candidate libraries: same county first, then state
        candidates = []
        if county_state:
            candidates = county_libs.get(county_state, [])
        if not candidates and county_state:
            candidates = state_libs.get(county_state[1], [])

        if not candidates:
            no_match += 1
            continue

        # Sort by distance, take nearest up to MAX_LIBS_PER_ZIP within MAX_DISTANCE_MILES
        scored = []
        for clib in candidates:
            dist = haversine(zlat, zlng, clib["lat"], clib["lng"])
            if dist <= MAX_DISTANCE_MILES:
                scored.append((dist, clib["name"]))

        scored.sort()
        nearest = scored[:MAX_LIBS_PER_ZIP]

        if nearest:
            for _, name in nearest:
                zip_to_libs[zipcode].add(name)
            expanded += 1
        else:
            # All libraries in county are too far — take the single nearest anyway
            all_scored = [(haversine(zlat, zlng, c["lat"], c["lng"]), c["name"]) for c in candidates]
            all_scored.sort()
            zip_to_libs[zipcode].add(all_scored[0][1])
            expanded += 1

    print(f"  Expanded: {expanded} zipcodes mapped via proximity")
    print(f"  No coordinates: {no_coords}")
    print(f"  No candidate libraries: {no_match}")
    print(f"  Total zipcodes covered: {len(zip_to_libs)}")

    # Rebuild library zipcodes
    lib_zipcodes = defaultdict(set)
    for zipcode, lib_names in zip_to_libs.items():
        for name in lib_names:
            lib_zipcodes[name].add(zipcode)

    for name, lib in all_libs.items():
        if name in lib_zipcodes:
            lib["zipcodes"] = sorted(lib_zipcodes[name])

    # Rewrite prefix files
    prefix_groups = defaultdict(list)
    for name, lib in all_libs.items():
        for zipcode in lib["zipcodes"]:
            prefix = zipcode[:3]
            if not any(l["name"] == name for l in prefix_groups[prefix]):
                prefix_groups[prefix].append(lib)

    # Clear old data files first
    for filepath in glob.glob(os.path.join(data_dir, "libraries-*.json")):
        os.remove(filepath)

    for prefix, libs in prefix_groups.items():
        filepath = os.path.join(data_dir, f"libraries-{prefix}.json")
        with open(filepath, "w") as f:
            json.dump({"libraries": libs}, f, indent=2)

    print(f"  Wrote {len(prefix_groups)} prefix files")
    return len(zip_to_libs)


if __name__ == "__main__":
    data_dir = sys.argv[1] if len(sys.argv) > 1 else "data"
    zip_county_path = sys.argv[2] if len(sys.argv) > 2 else "scripts/raw_data/zip_county.csv"
    zip_coords_path = sys.argv[3] if len(sys.argv) > 3 else "scripts/raw_data/zip_coords.csv"
    imls_csv_path = sys.argv[4] if len(sys.argv) > 4 else "scripts/raw_data/CSV/PLS_FY23_AE_pud23i.csv"
    expand_zipcodes(data_dir, zip_county_path, zip_coords_path, imls_csv_path)
