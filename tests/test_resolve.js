const { describe, it } = require("node:test");
const assert = require("node:assert/strict");
const { validateAuth, validatePayload, mapLibrary } = require("../api/v1/library-requests/resolve.js");

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
