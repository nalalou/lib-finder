const fs = require("fs");
const path = require("path");
const crypto = require("crypto");

function validateAuth(authHeader, expectedKey) {
  if (!authHeader) return { status: 401, error: "Missing Authorization header." };
  const parts = authHeader.split(" ");
  if (parts.length !== 2 || parts[0] !== "Bearer") return { status: 401, error: "Invalid Authorization format. Use: Bearer <api_key>" };
  if (parts[1].length !== expectedKey.length || !crypto.timingSafeEqual(Buffer.from(parts[1]), Buffer.from(expectedKey))) return { status: 401, error: "Invalid API key." };
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
