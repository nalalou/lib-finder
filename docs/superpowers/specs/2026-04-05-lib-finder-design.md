# Library Finder — Design Spec

A minimal static site where users enter their zipcode and get directed to their local library's "request a purchase" form.

## Problem

Most public libraries let patrons request book purchases, but the forms are buried deep in library websites with no standard URL pattern. There's no central directory. Users give up before finding it.

## Solution

A single-page tool: enter zipcode, click, get redirected to the right form in a new tab. Data sourced from IMLS + agentic Playwright scraper. Community contributions fill the gaps.

---

## Architecture

### Static Site (Vercel Free Tier)

- Plain HTML/CSS/JS — no framework
- Single page with three states:
  1. **Default** — Hero text, big zipcode input, CTA button
  2. **Results** — Opens the library's form (or homepage) in a new tab. If multiple library systems serve that zip, show a brief picker
  3. **Submission prompt** — If we routed to a homepage (not a direct form URL), a small link appears: "Know the direct link? Submit it here." Expands inline — paste URL, click submit, done
- Fetches the relevant 3-digit prefix JSON file on lookup (e.g. `/data/libraries-900.json`)
- Auto-focus on input, inline validation (5-digit check, not-found errors), no modals
- Minimum 44x44px touch targets, mobile-friendly
- Distinctive minimal typography, bold hero, generous whitespace
- Collaborative feel — small note like "built and improved by librarians and readers"

### Data Pipeline

**IMLS Ingestion (Python script):**
- Download IMLS Public Libraries Survey dataset (CSV)
- Extract: library system name, address, zipcode(s) served, website URL
- Normalize into data model
- Output as 3-digit prefix JSON files in `/data/`

**Agentic Scraper (Python + Playwright, manual one-time run):**
- Takes library website URLs from IMLS data
- For each library:
  - Launches headless browser via Playwright
  - Navigates to the library's website
  - Searches the DOM for links/buttons matching patterns: "suggest a purchase", "request a title", "recommend a book", "purchase suggestion", etc.
  - Follows promising links, verifies the destination is a form page
  - Records the form URL + confidence level
  - Screenshots for verification if needed
- Claude orchestrates the logic — deciding what to click, handling edge cases
- Results written to structured output
- Libraries where no form is found: `formStatus: "unknown"`, linked to homepage

### Submission Flow

**On-site inline form:**
- Appears conditionally when we routed to a homepage (not a direct form)
- Fields: library context (pre-filled, read-only), URL paste field
- Honeypot hidden field for spam protection
- Submit button → Vercel serverless function

**Serverless function (Node, ~15 lines):**
- Validates URL server-side: must return 200, domain check (.gov, .org, .edu, .us, known library domains)
- Creates a GitHub Issue with structured labels: `submission`, library system name, zipcode
- Returns success/failure to UI

**Review pipeline:**
- Submissions land as GitHub Issues
- Maintainer reviews and labels `approved` or `rejected`
- GitHub Action on `approved` label:
  - Parses issue body
  - Updates the relevant 3-digit prefix JSON file
  - Commits change
  - Vercel auto-redeploys from the commit

Approved submissions become verified data — no separate "community" tier in the UI.

---

## Data Model

Each 3-digit prefix file (e.g. `libraries-900.json`) contains:

```json
{
  "libraries": [
    {
      "name": "Los Angeles Public Library",
      "system": "LAPL",
      "address": "630 W 5th St, Los Angeles, CA 90071",
      "website": "https://lapl.org",
      "formUrl": "https://lapl.org/suggest-a-purchase",
      "formStatus": "verified",
      "zipcodes": ["90012", "90013", "90014"]
    }
  ]
}
```

- `formUrl`: direct link to purchase request form (null if unknown)
- `formStatus`: `"verified"` (scraped + confirmed, or approved submission) or `"unknown"` (homepage only)
- `zipcodes`: array of zipcodes served by this library system
- Client-side filters to the exact zipcode after fetching the prefix file

---

## Tech Stack

| Component | Technology |
|---|---|
| Site | Plain HTML/CSS/JS |
| Hosting | Vercel free tier |
| Data files | Static JSON, split by 3-digit zipcode prefix |
| Scraper | Python + Playwright (manual, one-time) |
| IMLS ingestion | Python script |
| Submissions | Vercel serverless function (Node) → GitHub Issues |
| Review pipeline | GitHub Action (on issue label) |
| Version control | Git + GitHub |

## Not In Scope

- No database
- No user accounts
- No recurring scraper schedule
- No frontend framework (React, Next.js, etc.)
- No analytics
- Naming/branding (deferred)
