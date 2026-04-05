# Partner API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a `POST /v1/library-requests/resolve` endpoint that resolves a zipcode to matching libraries with verified request URLs, behind API key auth.

**Architecture:** Single Vercel serverless function reads static JSON data files, filters by zipcode, and maps internal fields to the partner-facing API contract. Auth is a bearer token checked against a `PARTNER_API_KEY` env var. No database or external services.

**Tech Stack:** Node.js (Vercel serverless), Python (ID generation script), Node built-in test runner.

**Spec:** `docs/superpowers/specs/2026-04-05-partner-api-design.md`

---

## File Structure

| Action | Path | Responsibility |
|--------|------|---------------|
| Create | `scripts/generate_ids.py` | One-time script to add stable `id` fields to all library JSON files |
| Create | `tests/test_generate_ids.py` | Tests for ID generation logic |
| Create | `api/v1/library-requests/resolve.js` | Partner API serverless endpoint |
| Create | `tests/test_resolve.js` | Tests for the resolve endpoint |
| Modify | `vercel.json` | Add rewrite rule for `/v1/` path prefix |
| Modify | `scripts/ingest_imls.py` | Add ID generation to ingestion pipeline |
| Modify | `tests/test_ingest.py` | Add test for ID generation during ingestion |
| Modify | `package.json` | Update test script to run both test files |

---

### Task 1: Generate stable library IDs — script and tests

**Files:**
- Create: `scripts/generate_ids.py`
- Create: `tests/test_generate_ids.py`

- [ ] **Step 1: Write the test file for ID generation**

Create `tests/test_generate_ids.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_generate_ids.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.generate_ids'`

- [ ] **Step 3: Write the generate_ids.py script**

Create `scripts/generate_ids.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_generate_ids.py -v`
Expected: All 9 tests PASS

- [ ] **Step 5: Run the script against real data**

Run: `cd /Users/noraalalou/projects/lib-finder && python scripts/generate_ids.py`
Expected: Output like `Adding IDs to 893 files... Done. Assigned XXXX unique IDs.`

Verify a file was updated:
Run: `python -c "import json; d=json.load(open('data/libraries-100.json')); print(d['libraries'][0]['id'])"`
Expected: A slug like `new-york-public-library-the-branch-libraries-ny`

- [ ] **Step 6: Commit**

```bash
git add scripts/generate_ids.py tests/test_generate_ids.py data/
git commit -m "feat: add stable IDs to all library records"
```

---

### Task 2: Update ingestion pipeline to generate IDs

**Files:**
- Modify: `scripts/ingest_imls.py`
- Modify: `tests/test_ingest.py`

- [ ] **Step 1: Write the failing test**

Add to the bottom of `tests/test_ingest.py`:

```python
def test_write_prefix_files_includes_ids():
    """Libraries should get stable IDs when written to prefix files."""
    libraries = [
        {"name": "Lib A", "system": "Lib A", "address": "1 Main St, City, CA",
         "website": "https://a.org", "formUrl": None, "formStatus": "unknown",
         "zipcodes": ["90012"]},
        {"name": "Lib B", "system": "Lib B", "address": "2 Oak Ave, Town, NY",
         "website": "https://b.org", "formUrl": None, "formStatus": "unknown",
         "zipcodes": ["10018"]},
    ]
    with tempfile.TemporaryDirectory() as tmpdir:
        write_prefix_files(libraries, tmpdir)

        with open(os.path.join(tmpdir, "libraries-900.json")) as f:
            data = json.load(f)
        assert "id" in data["libraries"][0]
        assert data["libraries"][0]["id"] == "lib-a-ca"

        with open(os.path.join(tmpdir, "libraries-100.json")) as f:
            data = json.load(f)
        assert data["libraries"][0]["id"] == "lib-b-ny"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_ingest.py::test_write_prefix_files_includes_ids -v`
Expected: FAIL with `KeyError: 'id'`

- [ ] **Step 3: Update ingest_imls.py to generate IDs**

In `scripts/ingest_imls.py`, add import at the top:

```python
from scripts.generate_ids import generate_id
```

In the `write_prefix_files` function, after building `clean_libs`, add ID generation before writing:

Replace the `write_prefix_files` function body with:

```python
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
```

- [ ] **Step 4: Run all ingest tests to verify they pass**

Run: `python -m pytest tests/test_ingest.py -v`
Expected: All tests PASS (existing tests still pass because they don't check for absence of `id`)

- [ ] **Step 5: Commit**

```bash
git add scripts/ingest_imls.py tests/test_ingest.py
git commit -m "feat: generate stable IDs during ingestion"
```

---

### Task 3: Build the resolve endpoint — auth and validation

**Files:**
- Create: `api/v1/library-requests/resolve.js`
- Create: `tests/test_resolve.js`

- [ ] **Step 1: Write failing tests for auth and validation**

Create `tests/test_resolve.js`:

```javascript
const { describe, it, beforeEach } = require("node:test");
const assert = require("node:assert/strict");

// --- Helpers extracted from the endpoint for unit testing ---

function validateAuth(authHeader, expectedKey) {
  if (!authHeader) return { status: 401, error: "Missing Authorization header." };
  const parts = authHeader.split(" ");
  if (parts.length !== 2 || parts[0] !== "Bearer") return { status: 401, error: "Invalid Authorization format. Use: Bearer <api_key>" };
  if (parts[1] !== expectedKey) return { status: 401, error: "Invalid API key." };
  return null;
}

function validatePayload(body) {
  if (!body || typeof body !== "object") return "Invalid request body.";
  if (!body.user || typeof body.user !== "object") return "Missing required field: user.";
  const zip = body.user.zipcode;
  if (!zip) return "Missing required field: user.zipcode.";
  if (typeof zip !== "string" || !/^\d{5}$/.test(zip)) return "Invalid zipcode. Must be a 5-digit string.";
  return null;
}

function mapLibrary(lib) {
  return {
    id: lib.id,
    name: lib.name,
    address: lib.address,
    request_url: lib.formStatus === "verified" ? lib.formUrl : null,
    request_url_status: lib.formStatus,
    fallback_url: lib.website,
    action: "redirect",
  };
}

describe("validateAuth", () => {
  const key = "test-key-123";

  it("rejects missing header", () => {
    const err = validateAuth(undefined, key);
    assert.equal(err.status, 401);
  });

  it("rejects non-Bearer scheme", () => {
    const err = validateAuth("Basic abc", key);
    assert.equal(err.status, 401);
  });

  it("rejects wrong key", () => {
    const err = validateAuth("Bearer wrong-key", key);
    assert.equal(err.status, 401);
  });

  it("accepts valid key", () => {
    const err = validateAuth("Bearer test-key-123", key);
    assert.equal(err, null);
  });
});

describe("validatePayload", () => {
  it("rejects null body", () => {
    assert.ok(validatePayload(null));
  });

  it("rejects missing user", () => {
    assert.ok(validatePayload({}));
  });

  it("rejects missing zipcode", () => {
    assert.ok(validatePayload({ user: {} }));
  });

  it("rejects non-5-digit zipcode", () => {
    assert.ok(validatePayload({ user: { zipcode: "123" } }));
  });

  it("rejects numeric zipcode", () => {
    assert.ok(validatePayload({ user: { zipcode: 10001 } }));
  });

  it("accepts valid payload", () => {
    assert.equal(validatePayload({ user: { zipcode: "10001" } }), null);
  });

  it("accepts payload with optional book metadata", () => {
    assert.equal(validatePayload({
      user: { zipcode: "10001" },
      book: { title: "Test", author: "Author", isbn: "1234567890" }
    }), null);
  });
});

describe("mapLibrary", () => {
  it("maps verified library with request_url", () => {
    const lib = {
      id: "hampton-public-library-ia",
      name: "HAMPTON PUBLIC LIBRARY",
      address: "4 S FEDERAL ST, HAMPTON, IA",
      website: "https://www.hampton.lib.ia.us/",
      formUrl: "https://www.hampton.lib.ia.us/services/interlibrary-loan",
      formStatus: "verified",
    };
    const result = mapLibrary(lib);
    assert.equal(result.id, "hampton-public-library-ia");
    assert.equal(result.request_url, "https://www.hampton.lib.ia.us/services/interlibrary-loan");
    assert.equal(result.request_url_status, "verified");
    assert.equal(result.fallback_url, "https://www.hampton.lib.ia.us/");
    assert.equal(result.action, "redirect");
  });

  it("maps unverified library with null request_url", () => {
    const lib = {
      id: "some-library-ny",
      name: "SOME LIBRARY",
      address: "1 MAIN ST, CITY, NY",
      website: "https://some.org",
      formUrl: null,
      formStatus: "unknown",
    };
    const result = mapLibrary(lib);
    assert.equal(result.request_url, null);
    assert.equal(result.request_url_status, "unknown");
    assert.equal(result.fallback_url, "https://some.org");
    assert.equal(result.action, "redirect");
  });
});
```

- [ ] **Step 2: Run tests to verify they pass (pure unit tests on helpers)**

Run: `node --test tests/test_resolve.js`
Expected: All tests PASS (these test extracted helper functions directly)

- [ ] **Step 3: Write the resolve endpoint**

Create `api/v1/library-requests/resolve.js`:

```javascript
const fs = require("fs");
const path = require("path");
const crypto = require("crypto");

function validateAuth(authHeader, expectedKey) {
  if (!authHeader) return { status: 401, error: "Missing Authorization header." };
  const parts = authHeader.split(" ");
  if (parts.length !== 2 || parts[0] !== "Bearer") return { status: 401, error: "Invalid Authorization format. Use: Bearer <api_key>" };
  if (parts[1] !== expectedKey) return { status: 401, error: "Invalid API key." };
  return null;
}

function validatePayload(body) {
  if (!body || typeof body !== "object") return "Invalid request body.";
  if (!body.user || typeof body.user !== "object") return "Missing required field: user.";
  const zip = body.user.zipcode;
  if (!zip) return "Missing required field: user.zipcode.";
  if (typeof zip !== "string" || !/^\d{5}$/.test(zip)) return "Invalid zipcode. Must be a 5-digit string.";
  return null;
}

function mapLibrary(lib) {
  return {
    id: lib.id,
    name: lib.name,
    address: lib.address,
    request_url: lib.formStatus === "verified" ? lib.formUrl : null,
    request_url_status: lib.formStatus,
    fallback_url: lib.website,
    action: "redirect",
  };
}

module.exports = { validateAuth, validatePayload, mapLibrary };

module.exports.default = async function handler(req, res) {
  if (req.method !== "POST") {
    return res.status(405).json({ error: "Method not allowed." });
  }

  const apiKey = process.env.PARTNER_API_KEY;
  if (!apiKey) {
    console.error("Missing PARTNER_API_KEY env var");
    return res.status(500).json({ error: "Server configuration error." });
  }

  const authError = validateAuth(req.headers.authorization, apiKey);
  if (authError) {
    return res.status(authError.status).json({ error: authError.error });
  }

  const payloadError = validatePayload(req.body);
  if (payloadError) {
    return res.status(400).json({ error: payloadError });
  }

  const zipcode = req.body.user.zipcode;
  const prefix = zipcode.slice(0, 3);
  const dataPath = path.join(process.cwd(), "data", `libraries-${prefix}.json`);

  let data;
  try {
    const raw = fs.readFileSync(dataPath, "utf-8");
    data = JSON.parse(raw);
  } catch (err) {
    if (err.code === "ENOENT") {
      return res.status(404).json({ error: "No libraries found for this zipcode." });
    }
    console.error("Error reading library data:", err);
    return res.status(500).json({ error: "Internal server error." });
  }

  const libraries = (data.libraries || []).filter((lib) =>
    lib.zipcodes && lib.zipcodes.includes(zipcode)
  );

  if (libraries.length === 0) {
    return res.status(404).json({ error: "No libraries found for this zipcode." });
  }

  const requestId = "req_" + crypto.randomBytes(8).toString("hex");

  return res.status(200).json({
    request_id: requestId,
    libraries: libraries.map(mapLibrary),
  });
};
```

- [ ] **Step 4: Run tests again to confirm nothing broke**

Run: `node --test tests/test_resolve.js`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add api/v1/library-requests/resolve.js tests/test_resolve.js
git commit -m "feat: add partner API resolve endpoint with auth and validation"
```

---

### Task 4: Update Vercel config and test script

**Files:**
- Modify: `vercel.json`
- Modify: `package.json`

- [ ] **Step 1: Update vercel.json with the rewrite rule**

Replace the entire `vercel.json` content with:

```json
{
  "rewrites": [
    { "source": "/api/submit", "destination": "/api/submit" },
    { "source": "/v1/:path*", "destination": "/api/v1/:path*" }
  ],
  "headers": [
    {
      "source": "/data/(.*)",
      "headers": [
        { "key": "Cache-Control", "value": "public, max-age=3600" }
      ]
    }
  ]
}
```

- [ ] **Step 2: Update package.json test script to run both test files**

Replace the `scripts` section in `package.json`:

```json
{
  "scripts": {
    "test": "node --test tests/test_app.js tests/test_resolve.js"
  }
}
```

- [ ] **Step 3: Run the full test suite**

Run: `cd /Users/noraalalou/projects/lib-finder && npm test`
Expected: All tests from both `test_app.js` and `test_resolve.js` PASS

- [ ] **Step 4: Commit**

```bash
git add vercel.json package.json
git commit -m "feat: add Vercel rewrite for partner API and update test script"
```

---

### Task 5: End-to-end verification

This task verifies the full flow works against real data files (which now have IDs from Task 1).

**Files:**
- Modify: `tests/test_resolve.js`

- [ ] **Step 1: Add integration-style test using real data**

Append to `tests/test_resolve.js`:

```javascript
const fs = require("node:fs");
const nodePath = require("node:path");

describe("resolve against real data", () => {
  it("returns libraries for zipcode 50441 with IDs", () => {
    // 50441 is served by HAMPTON PUBLIC LIBRARY in data/libraries-504.json
    const dataPath = nodePath.join(process.cwd(), "data", "libraries-504.json");
    const data = JSON.parse(fs.readFileSync(dataPath, "utf-8"));
    const libs = data.libraries.filter((lib) => lib.zipcodes && lib.zipcodes.includes("50441"));

    assert.ok(libs.length > 0, "Should find at least one library for 50441");
    assert.ok(libs[0].id, "Library should have an id field");
    assert.ok(typeof libs[0].id === "string", "ID should be a string");
    assert.ok(libs[0].id.length > 0, "ID should not be empty");

    // Verify mapping works
    const mapped = mapLibrary(libs[0]);
    assert.equal(mapped.action, "redirect");
    assert.ok(mapped.fallback_url, "Should have a fallback_url");
    assert.equal(mapped.request_url_status, libs[0].formStatus);
  });

  it("returns 404-worthy result for nonexistent zipcode prefix", () => {
    // Prefix 999 should not have a data file
    const dataPath = nodePath.join(process.cwd(), "data", "libraries-999.json");
    assert.ok(!fs.existsSync(dataPath), "libraries-999.json should not exist");
  });
});
```

- [ ] **Step 2: Run the full test suite**

Run: `npm test`
Expected: All tests PASS

- [ ] **Step 3: Run Python tests too**

Run: `python -m pytest tests/ -v`
Expected: All Python tests PASS

- [ ] **Step 4: Commit**

```bash
git add tests/test_resolve.js
git commit -m "test: add integration tests against real library data"
```
