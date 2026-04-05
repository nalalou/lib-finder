# Partner API Integration Guide

## Overview

The lib-finder Partner API lets you resolve a reader's zipcode to matching libraries with verified book-request URLs. You own the frontend. We handle library discovery and request-page routing.

**Base URL:** `https://lib-finder.vercel.app`

**Auth:** Bearer token in the `Authorization` header. You'll receive your API key from the lib-finder team.

## Quick Start

```bash
curl -X POST https://lib-finder.vercel.app/v1/library-requests/resolve \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "user": { "zipcode": "50441" },
    "book": { "title": "Intermezzo", "author": "Sally Rooney", "isbn": "9780374602642" }
  }'
```

## Endpoint

### `POST /v1/library-requests/resolve`

Resolves a zipcode to one or more libraries. Returns verified request-page URLs when available, or the library website as a fallback.

### Request

```json
{
  "user": {
    "zipcode": "10001"
  },
  "book": {
    "title": "Intermezzo",
    "author": "Sally Rooney",
    "isbn": "9780374602642"
  }
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `user.zipcode` | string | Yes | 5-digit US ZIP code |
| `book.title` | string | No | Book title |
| `book.author` | string | No | Book author |
| `book.isbn` | string | No | ISBN-10 or ISBN-13 |

`book` is entirely optional. It is logged for analytics but does not affect which libraries are returned.

### Response

```json
{
  "request_id": "req_a1b2c3d4e5f6g7h8",
  "libraries": [
    {
      "id": "hampton-public-library-ia",
      "name": "HAMPTON PUBLIC LIBRARY",
      "address": "4 S FEDERAL ST, HAMPTON, IA",
      "request_url": "https://www.hampton.lib.ia.us/services/interlibrary-loan",
      "request_url_status": "verified",
      "fallback_url": "https://www.hampton.lib.ia.us/",
      "action": "redirect"
    }
  ]
}
```

| Field | Type | Description |
|-------|------|-------------|
| `request_id` | string | Unique ID for this request (for support/debugging) |
| `libraries` | array | One or more matching libraries |
| `libraries[].id` | string | Stable library identifier |
| `libraries[].name` | string | Library name |
| `libraries[].address` | string | Library address |
| `libraries[].request_url` | string or null | Direct link to the library's book request page. `null` if not verified. |
| `libraries[].request_url_status` | string | One of: `verified`, `unknown`, `broken`, `unavailable` |
| `libraries[].fallback_url` | string | Library website. Always present. |
| `libraries[].action` | string | Always `"redirect"` in v1 |

### Routing Logic

For each library in the response:

- If `request_url` is not null, send the reader there. It is a verified request page.
- If `request_url` is null, send the reader to `fallback_url` (the library's website).

Do not use `request_url_status` to decide routing. Use the presence/absence of `request_url`. The status field is informational.

### Errors

| HTTP Status | Meaning | Example |
|-------------|---------|---------|
| 400 | Bad request | Missing zipcode, invalid format |
| 401 | Unauthorized | Missing or invalid API key |
| 404 | Not found | No libraries serve this zipcode |
| 405 | Method not allowed | Used GET instead of POST |
| 500 | Server error | Misconfiguration or internal failure |

Error responses have the shape:

```json
{
  "error": "Human-readable error message."
}
```

## Integration Patterns

### Server-to-Server (Recommended)

Call the API from your backend. This keeps the API key off the client.

```javascript
// Node.js example
const response = await fetch("https://lib-finder.vercel.app/v1/library-requests/resolve", {
  method: "POST",
  headers: {
    "Authorization": "Bearer " + process.env.LIB_FINDER_API_KEY,
    "Content-Type": "application/json",
  },
  body: JSON.stringify({
    user: { zipcode: req.body.zipcode },
    book: { title: "Intermezzo", author: "Sally Rooney" },
  }),
});

const data = await response.json();

if (!response.ok) {
  // data.error contains the message
  return res.status(response.status).json({ error: data.error });
}

// data.libraries is the array to render
```

### Typical User Flow

1. Reader clicks "Request this book at your library" on your site
2. Your UI asks for their zipcode
3. Your backend calls the API with the zipcode (and optionally the book metadata)
4. You display the returned libraries
5. Reader clicks a library. You open `request_url` (if present) or `fallback_url` in a new tab

### Handling Multiple Libraries

A zipcode can match multiple library systems. Display all of them and let the reader choose. Libraries with a `request_url` should be visually prioritized (they lead directly to the request page).

## Constraints

- **No form submission.** The API routes readers to the right page. It does not submit forms or prefill data.
- **No CORS.** The API is server-to-server only in v1. Do not call it from browser JavaScript.
- **Library data updates with deploys.** Request URLs are curated, not scraped in real-time. If a URL breaks, report it and we'll update on the next deploy.
- **US libraries only.** Zipcode matching covers US ZIP codes.

## Reporting Issues

If a `request_url` is broken or leads to the wrong page, email the `request_id` and library `id` to the lib-finder team so we can investigate and update the dataset.
