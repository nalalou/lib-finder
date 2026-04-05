export default async function handler(req, res) {
  if (req.method !== "POST") {
    return res.status(405).json({ error: "Method not allowed" });
  }

  const { zipcode, libraryName, formUrl } = req.body || {};

  if (!zipcode || !libraryName || !formUrl) {
    return res.status(400).json({ error: "Missing required fields." });
  }

  let parsedUrl;
  try {
    parsedUrl = new URL(formUrl);
  } catch {
    return res.status(400).json({ error: "Invalid URL format." });
  }

  const hostname = parsedUrl.hostname.toLowerCase();
  const allowedTLDs = [".gov", ".org", ".edu", ".us", ".lib"];
  const hasAllowedTLD = allowedTLDs.some((tld) => hostname.endsWith(tld));
  const isKnownLibraryDomain =
    hostname.includes("library") ||
    hostname.includes("bibliocommons") ||
    hostname.includes("librarycat");

  if (!hasAllowedTLD && !isKnownLibraryDomain) {
    return res.status(400).json({
      error: "URL must be from a library domain (.gov, .org, .edu, .us, or a known library site).",
    });
  }

  try {
    const check = await fetch(formUrl, {
      method: "HEAD",
      redirect: "follow",
      signal: AbortSignal.timeout(10000),
    });
    if (!check.ok) {
      return res.status(400).json({ error: "URL does not appear to be reachable." });
    }
  } catch {
    return res.status(400).json({ error: "Could not reach the URL. Please check and try again." });
  }

  const ghToken = process.env.GITHUB_TOKEN;
  const ghRepo = process.env.GITHUB_REPO;

  if (!ghToken || !ghRepo) {
    console.error("Missing GITHUB_TOKEN or GITHUB_REPO env vars");
    return res.status(500).json({ error: "Server configuration error." });
  }

  const issueTitle = `[submission] ${libraryName} (${zipcode})`;
  const issueBody = [
    `**Library:** ${libraryName}`,
    `**Zipcode:** ${zipcode}`,
    `**Submitted URL:** ${formUrl}`,
    "",
    "---",
    "To approve, add the `approved` label to this issue.",
  ].join("\n");

  try {
    const ghResponse = await fetch(
      `https://api.github.com/repos/${ghRepo}/issues`,
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${ghToken}`,
          Accept: "application/vnd.github+json",
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          title: issueTitle,
          body: issueBody,
          labels: ["submission"],
        }),
      }
    );

    if (!ghResponse.ok) {
      const ghError = await ghResponse.text();
      console.error("GitHub API error:", ghError);
      return res.status(500).json({ error: "Failed to create submission." });
    }

    return res.status(200).json({ success: true });
  } catch (err) {
    console.error("GitHub API error:", err);
    return res.status(500).json({ error: "Failed to create submission." });
  }
}
