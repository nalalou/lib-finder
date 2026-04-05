import json
import glob
import os
import re


def slugify(name):
    """Convert a library name to a URL-safe slug."""
    s = name.lower().strip()
    s = re.sub(r"[^a-z0-9\s-]", "", s)
    s = re.sub(r"\s+", "-", s).strip("-")
    return s


def extract_state(address):
    """Extract the two-letter state abbreviation from an address like '1 MAIN ST, CITY, CA'."""
    parts = [p.strip() for p in address.split(",")]
    if len(parts) >= 3:
        return parts[-1].lower().strip()
    return None


def generate_id(name, address):
    """Generate a slug ID from library name and state."""
    slug = slugify(name)
    state = extract_state(address)
    if state:
        return f"{slug}-{state}"
    return slug


def add_ids_to_file(filepath, seen):
    """Add unique IDs to all libraries in a JSON file.

    Args:
        filepath: Path to a libraries-XXX.json file.
        seen: Dict tracking all assigned IDs across files. Mutated in place.
    """
    with open(filepath) as f:
        data = json.load(f)

    for lib in data.get("libraries", []):
        base_id = generate_id(lib["name"], lib["address"])
        final_id = base_id
        counter = 2
        while final_id in seen:
            final_id = f"{base_id}-{counter}"
            counter += 1
        seen[final_id] = True
        lib["id"] = final_id

    with open(filepath, "w") as f:
        json.dump(data, f, indent=2)


if __name__ == "__main__":
    data_dir = os.path.join(os.path.dirname(__file__), "..", "data")
    files = sorted(glob.glob(os.path.join(data_dir, "libraries-*.json")))
    print(f"Adding IDs to {len(files)} files...")

    seen = {}
    for filepath in files:
        add_ids_to_file(filepath, seen)

    print(f"Done. Assigned {len(seen)} unique IDs.")
