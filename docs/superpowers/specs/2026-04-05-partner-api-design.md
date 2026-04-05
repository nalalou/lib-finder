# Partner API Design Spec

## Overview

A single Vercel serverless endpoint that lets a partner site resolve a reader's zipcode to matching libraries with verified request URLs or fallback websites. No database, no external services — just a serverless function reading existing static JSON files behind API key auth.

## Architecture

```
Partner Request → Auth Check (env var) → Read JSON → Filter → Map → Response
```

One serverless function at `/api/v1/library-requests/resolve.js`:

1. Validates bearer token against `PARTNER_API_KEY` env var
2. Validates the request payload (zipcode required, book metadata optional)
3. Reads `/data/libraries-XXX.json` by 3-digit ZIP prefix
4. Filters libraries matching the exact 5-digit zipcode
5. Maps internal fields to API response contract
6. Returns results

No database, no Redis, no paid services. Same static-JSON-read pattern as the existing frontend, behind auth.

## Data Changes

### Stable Library IDs

Add an `id` field to every library record in the JSON files. Format: slugified `name` + `-` + two-letter state abbreviation extracted from the address.

Example:

```json
{
  "id": "hampton-public-library-ia",
  "name": "HAMPTON PUBLIC LIBRARY",
  "system": "HAMPTON PUBLIC LIBRARY",
  "address": "4 S FEDERAL ST, HAMPTON, IA",
  "website": "https://www.hampton.lib.ia.us/",
  "formUrl": "https://www.hampton.lib.ia.us/services/interlibrary-loan",
  "formStatus": "verified",
  "zipcodes": ["50441"]
}
```

Collision handling: append `-2`, `-3`, etc. when multiple libraries in the same state produce the same slug.

### Scripts

- `scripts/generate_ids.py` — one-time script to add IDs to all existing JSON files
- `scripts/ingest_imls.py` — updated to generate IDs during ingestion so future runs include them

Adding `id` is backward-compatible; the frontend ignores fields it doesn't use.

## API Contract

### Endpoint

`POST /v1/library-requests/resolve`

### Authentication

`Authorization: Bearer <api_key>`

Single API key stored as `PARTNER_API_KEY` environment variable in Vercel.

### Request

```json
{
  "user": { "zipcode": "10001" },
  "book": {
    "title": "Example Book",
    "author": "Example Author",
    "isbn": "9781234567890"
  }
}
```

- `user.zipcode` — required, 5-digit US ZIP code
- `book` — entirely optional, passed through for logging, not used in matching for v1

### Response (200)

```json
{
  "request_id": "req_abc123",
  "libraries": [
    {
      "id": "new-york-public-library-ny",
      "name": "New York Public Library",
      "address": "476 Fifth Avenue, New York, NY",
      "request_url": "https://example.org/request",
      "request_url_status": "verified",
      "fallback_url": "https://www.nypl.org",
      "action": "redirect"
    }
  ]
}
```

### Response Mapper

| Internal field | API field | Notes |
|---|---|---|
| `id` | `id` | |
| `name` | `name` | |
| `address` | `address` | |
| `formUrl` | `request_url` | Set to the URL when `formStatus === "verified"`, otherwise `null` |
| `formStatus` | `request_url_status` | |
| `website` | `fallback_url` | |
| _(hardcoded)_ | `action` | Always `"redirect"` in v1 |

`request_id` is generated per request as `req_` + random hex. For log correlation only, not persisted.

### Errors

| Code | Condition |
|---|---|
| 400 | Invalid/missing zipcode, malformed payload |
| 401 | Missing or invalid API key |
| 404 | No libraries found for zipcode |
| 500 | Internal error |

403 (suspended partner) and 429 (rate limit) are deferred — not needed for a single trusted partner.

## File Structure

### New files

```
api/v1/library-requests/resolve.js   # Serverless endpoint
scripts/generate_ids.py               # One-time ID generation
```

### Modified files

```
vercel.json                           # Add rewrite for /v1/ path
scripts/ingest_imls.py                # Generate IDs during ingestion
```

### Vercel config

```json
{
  "rewrites": [
    { "source": "/api/submit", "destination": "/api/submit" },
    { "source": "/v1/:path*", "destination": "/api/v1/:path*" }
  ]
}
```

Partners call `/v1/library-requests/resolve` (clean URL). Vercel routes to the serverless function.

### Environment variable

- `PARTNER_API_KEY` — set in Vercel dashboard

### No new dependencies

The endpoint uses Node.js built-ins (`fs`, `path`, `crypto`).

## Testing

New test file: `tests/test_resolve.js` using Node's built-in test runner (matching existing pattern).

Coverage:

- **Auth**: missing token returns 401, invalid token returns 401, valid token proceeds
- **Validation**: missing zipcode returns 400, non-5-digit zipcode returns 400, malformed JSON returns 400
- **Lookup**: valid zipcode returns matching libraries, zipcode with no matches returns 404
- **Response mapping**: verified formUrl populates `request_url`, non-verified sets `request_url` to null, `fallback_url` always present, `action` always `"redirect"`
- **ID generation**: slugs are correct, collisions get suffixes, all records get IDs

No mocking — the function reads static JSON files that already exist in the repo.

## Assumptions

- Library data updates are infrequent and can tolerate deploy-cycle latency
- One partner for v1; partner management infrastructure deferred until more partners exist
- Book metadata is logged but not used for matching in v1
- Rate limiting and partner suspension are not needed for a single trusted partner

## Future Migration Path

When more partners are onboarded:

1. Add Neon Postgres for partner accounts, API keys, usage logs
2. Add Upstash Redis for rate limiting
3. If library data needs faster updates, migrate to Postgres alongside partner data
