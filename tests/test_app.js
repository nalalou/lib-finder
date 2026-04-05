const { describe, it } = require("node:test");
const assert = require("node:assert/strict");

function validateZipcode(zip) {
  if (!zip || zip.length !== 5) return "Please enter a 5-digit zipcode.";
  if (!/^\d{5}$/.test(zip)) return "Zipcode must be 5 digits.";
  return null;
}

function getPrefix(zip) {
  return zip.slice(0, 3);
}

function findLibraries(data, zip) {
  if (!data || !data.libraries) return [];
  return data.libraries.filter((lib) =>
    lib.zipcodes.includes(zip)
  );
}

function getLibraryUrl(library) {
  return library.formUrl || library.website;
}

function needsSubmitPrompt(library) {
  return library.formStatus === "unknown";
}

describe("validateZipcode", () => {
  it("returns null for valid zipcode", () => {
    assert.equal(validateZipcode("90210"), null);
  });

  it("rejects short input", () => {
    assert.equal(validateZipcode("9021"), "Please enter a 5-digit zipcode.");
  });

  it("rejects non-numeric input", () => {
    assert.equal(validateZipcode("9021a"), "Zipcode must be 5 digits.");
  });

  it("rejects empty input", () => {
    assert.equal(validateZipcode(""), "Please enter a 5-digit zipcode.");
  });
});

describe("getPrefix", () => {
  it("returns first 3 digits", () => {
    assert.equal(getPrefix("90210"), "902");
  });
});

describe("findLibraries", () => {
  const data = {
    libraries: [
      { name: "Lib A", zipcodes: ["90210", "90211"] },
      { name: "Lib B", zipcodes: ["90212"] },
      { name: "Lib C", zipcodes: ["90210"] },
    ],
  };

  it("finds all libraries for a zipcode", () => {
    const results = findLibraries(data, "90210");
    assert.equal(results.length, 2);
    assert.equal(results[0].name, "Lib A");
    assert.equal(results[1].name, "Lib C");
  });

  it("returns empty array for unknown zipcode", () => {
    const results = findLibraries(data, "00000");
    assert.equal(results.length, 0);
  });

  it("handles null data", () => {
    assert.deepEqual(findLibraries(null, "90210"), []);
  });
});

describe("getLibraryUrl", () => {
  it("returns formUrl when available", () => {
    assert.equal(
      getLibraryUrl({ formUrl: "https://lib.org/form", website: "https://lib.org" }),
      "https://lib.org/form"
    );
  });

  it("falls back to website when formUrl is null", () => {
    assert.equal(
      getLibraryUrl({ formUrl: null, website: "https://lib.org" }),
      "https://lib.org"
    );
  });
});

describe("needsSubmitPrompt", () => {
  it("returns true for unknown formStatus", () => {
    assert.equal(needsSubmitPrompt({ formStatus: "unknown" }), true);
  });

  it("returns false for verified formStatus", () => {
    assert.equal(needsSubmitPrompt({ formStatus: "verified" }), false);
  });
});
