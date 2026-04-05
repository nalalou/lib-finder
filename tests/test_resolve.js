const { describe, it, before } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const nodePath = require("node:path");

let validateAuth, validatePayload, mapLibrary;

before(async () => {
  const mod = await import("../api/v1/library-requests/resolve.js");
  validateAuth = mod.validateAuth;
  validatePayload = mod.validatePayload;
  mapLibrary = mod.mapLibrary;
});

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

describe("resolve against real data", () => {
  it("returns libraries for zipcode 50441 with IDs", () => {
    const dataPath = nodePath.join(process.cwd(), "data", "libraries-504.json");
    const data = JSON.parse(fs.readFileSync(dataPath, "utf-8"));
    const libs = data.libraries.filter((lib) => lib.zipcodes && lib.zipcodes.includes("50441"));

    assert.ok(libs.length > 0, "Should find at least one library for 50441");
    assert.ok(libs[0].id, "Library should have an id field");
    assert.ok(typeof libs[0].id === "string", "ID should be a string");
    assert.ok(libs[0].id.length > 0, "ID should not be empty");

    const mapped = mapLibrary(libs[0]);
    assert.equal(mapped.action, "redirect");
    assert.ok(mapped.fallback_url, "Should have a fallback_url");
    assert.equal(mapped.request_url_status, libs[0].formStatus);
  });

  it("returns 404-worthy result for nonexistent zipcode prefix", () => {
    const dataPath = nodePath.join(process.cwd(), "data", "libraries-000.json");
    assert.ok(!fs.existsSync(dataPath), "libraries-000.json should not exist");
  });
});
