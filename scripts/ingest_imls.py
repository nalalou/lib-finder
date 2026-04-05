import csv
import json
import os


def parse_imls_csv(csv_path):
    """Parse IMLS Public Libraries Survey CSV into library records."""
    libraries = []
    with open(csv_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            website = row.get("WEBSITE", "").strip()
            if not website:
                continue
            if not website.startswith("http"):
                website = "https://" + website
            libraries.append({
                "name": row["LIBNAME"].strip(),
                "system": row["LIBNAME"].strip(),
                "address": f"{row['ADDRESS'].strip()}, {row['CITY'].strip()}, {row['STABR'].strip()}",
                "website": website,
                "formUrl": None,
                "formStatus": "unknown",
                "zipcodes": [row["ZIP"].strip()[:5]],
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
    for prefix, libs in groups.items():
        filepath = os.path.join(output_dir, f"libraries-{prefix}.json")
        with open(filepath, "w") as f:
            json.dump({"libraries": libs}, f, indent=2)
    return list(groups.keys())


if __name__ == "__main__":
    import sys
    csv_path = sys.argv[1] if len(sys.argv) > 1 else "scripts/raw_data/imls_systems.csv"
    output_dir = sys.argv[2] if len(sys.argv) > 2 else "data"
    libraries = parse_imls_csv(csv_path)
    prefixes = write_prefix_files(libraries, output_dir)
    print(f"Wrote {len(prefixes)} prefix files for {len(libraries)} libraries to {output_dir}/")
