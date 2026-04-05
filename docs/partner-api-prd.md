# PRD: Partner API for Library Request Routing

## Overview

Build a paid partner API that allows third-party sites, starting with author websites, to help readers find their library and navigate to the correct library book request page. Partners own the frontend experience. `lib-finder` provides authenticated library matching and request-page routing.

## Problem

Authors want a `Request this book at your library` experience on their own websites. Today, library request flows are fragmented across thousands of library systems, and readers often do not know which library serves them or where to submit a purchase request. A partner integration should solve discovery and routing without attempting to automate library-specific forms.

## Goal

Enable partner sites to:

- identify libraries serving a reader based on zipcode
- return a verified request page when available
- fall back to the library website when a verified request page is unavailable
- keep the full user experience on the partner's site until redirect

## Non-Goals

- No form prefilling
- No direct submission into library systems
- No embedded `lib-finder` UI
- No consumer billing in v1
- No guarantee that a library will purchase or process the request

## Users

- Primary: authors and publishers who want a library-request CTA on their site
- Secondary: readers trying to request a book from their library
- Internal: `lib-finder` operators maintaining request-link quality and partner accounts

## Value Proposition

For partners:

- quick integration
- no need to maintain library lookup infrastructure
- preserves their branding and site experience

For readers:

- less friction finding the right library
- better chance of reaching the correct request page

For `lib-finder`:

- monetizable B2B API product
- reusable infrastructure built on the existing library dataset

## Product Principles

- Keep the API narrow and reliable
- Route, do not automate
- Treat verified request URLs as curated data
- Make partner integration simple and stable
- Default to safe fallbacks when certainty is low

## User Story

As a reader on an author's site, I want to enter my zipcode and see which library serves me, so I can click through to the right page to request the book.

As a partner, I want to call an API and receive consistent library-routing data, so I can present the experience in my own UI.

## Primary Use Case

1. Reader clicks `Request this book at your library`.
2. Partner site asks for zipcode.
3. Partner calls the `lib-finder` API with zipcode and optional book metadata.
4. API returns one or more matching libraries.
5. Each result includes either:
   - a verified `request_url`, or
   - a fallback library website
6. Partner presents the results and sends the reader to the chosen destination.

## Requirements

### Functional Requirements

- Support authenticated partner access with API keys
- Accept a zipcode as required input
- Accept optional book metadata:
  - title
  - author
  - ISBN
- Return matching libraries for the zipcode
- Return a verified request URL when available
- Return the library website as fallback when no verified request URL exists
- Return multiple libraries if more than one serves the zipcode
- Provide clear status and error responses
- Log partner usage and request outcomes

### Data Requirements

Each library record should support:

- stable internal `id`
- `name`
- `address`
- `website`
- `requestUrl`
- `requestUrlStatus`

Suggested request URL statuses:

- `verified`
- `unknown`
- `broken`
- `unavailable`

### API Requirements

V1 endpoint:
`POST /v1/library-requests/resolve`

Request:

```json
{
  "user": {
    "zipcode": "10001"
  },
  "book": {
    "title": "Example Book",
    "author": "Example Author",
    "isbn": "9781234567890"
  }
}
```

Response:

```json
{
  "request_id": "req_123",
  "libraries": [
    {
      "id": "nypl",
      "name": "New York Public Library",
      "address": "476 Fifth Avenue, New York, NY",
      "request_url": "https://example.org/request",
      "request_url_status": "verified",
      "fallback_url": "https://www.nypl.org/locations",
      "action": "redirect"
    }
  ]
}
```

Behavior:

- if `request_url_status = verified`, include `request_url`
- otherwise partner should use `fallback_url`
- `action` is always `redirect` in v1

### Error Handling

- `400` invalid zipcode or malformed payload
- `401` missing or invalid API key
- `403` disabled or suspended partner
- `404` no matching libraries found
- `429` rate limit exceeded
- `500` internal server error

### Authentication and Access

- API key per partner
- bearer token auth
- rate limits by partner
- usage logs by partner and request
- preferably server-to-server access in v1

## Operational Workflow

Request URL quality must be curated, not inferred dynamically.

Internal workflow:

1. collect candidate request URLs from research or submissions
2. verify whether the URL is a valid request destination
3. update the library dataset
4. downgrade broken links when discovered
5. let the API automatically fall back to website if no verified link exists

## Success Metrics

Launch metrics:

- number of active partners
- number of API calls per partner
- percentage of lookups returning at least one library
- percentage of lookups returning a verified request URL
- clickthrough rate from partner UI to returned destination
- request URL failure reports

Quality metrics:

- low rate of broken verified URLs
- low support burden for partner integration
- low abuse and unauthorized usage

## Risks

- library request URLs can change frequently
- zipcode-to-library matching can produce multiple valid results
- browser-side integrations may expose API keys if not designed carefully
- partners may assume the API submits requests directly unless positioning is explicit

## Open Questions

- Should v1 support frontend CORS for approved domains, or backend-only integrations?
- Do we want to expose analytics to partners in v1 or later?
- How should multiple-library results be ranked?
- Do we need partner-specific branding or attribution requirements?

## MVP Scope

Ship:

- authenticated resolve endpoint
- verified request URL vs website fallback
- partner logging
- dataset support for request URL status
- basic docs and sample integration

Do not ship:

- prefill
- direct submission
- embedded widget
- partner dashboard unless needed for ops

## Launch Positioning

`Request this book at your library` for author websites.

External promise:

`We help your readers find the right library and get to the correct request page.`
