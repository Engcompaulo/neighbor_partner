*This is a submission for the [Hacktoberfest Open-Source AI Challenge Week 2: Side Hustle](https://dev.to/challenges/hacktoberfest-week2-2026-10-12)*

## What I Built

**Neighbor Partner** is a tiny web app that helps independent local shops find each other and cross-promote.

Every neighborhood is full of small businesses that are not competitors but could easily send each other customers: a bakery and a bookstore, a gym and a café, a florist and a photographer. The problem is discovery. Owners are busy running their shops and rarely know who is one block over, let alone which of those neighbors complements their business instead of competing with it.

Neighbor Partner solves that. A shop owner registers their shop in seconds (name, segment, target audience, neighborhood), browses the public list of registered shops, and opens any shop to see up to three AI-ranked **non-competing** partner suggestions in the same neighborhood. For any pair, one click generates a short promotional blurb they can drop straight into a window sign, a flyer, or an Instagram post.

**Who benefits:** local shop owners who want more foot traffic without an ad budget, and the neighborhoods that keep more of their trade local. It is the kind of lightweight tool a neighborhood association, a co-working space, or a chamber of commerce could host for its members for almost nothing.

The core safety rule — never suggest a competitor — is enforced in SQL (same neighborhood, different segment) *before* the AI ever sees the data. The model only reorders a candidate set that is already guaranteed to be safe.

## Demo

Run it locally with Docker (see the run steps below) and open **http://localhost:5000**.

On first start the app seeds a handful of example shops across two neighborhoods (Old Town and Riverside), each with multiple segments, so partner suggestions and promo blurbs work immediately without any manual setup.

## Code

All code lives in `desafio3/` and is deliberately small — three Python modules, three templates, one stylesheet, and a two-service Docker stack:

- `app.py` — Flask routes and app factory; orchestrates the DB and AI layers, validates the registration form, renders pages.
- `db.py` — SQLite lifecycle: schema init, first-run seeding, and queries. Owns the non-competing candidate query (`neighborhood = ? AND segment != ? AND id != ?`).
- `ai.py` — Ollama client. `suggest_partners()` ranks pre-filtered candidates; `generate_promo()` writes a short blurb. Both apply a 30s timeout and fall back to local heuristics, and neither ever raises.
- `templates/` — `base.html`, `index.html` (shop list + registration form), `suggestions.html` (partner cards + promo).
- `static/style.css` — one small responsive stylesheet.
- `Dockerfile` + `docker-compose.yml` — the `web` + `ollama` services.

## How I Built It

The whole thing is built on an open-source stack with a locally hosted model at its core:

- **Flask** serves the pages and handles form submissions, run under **gunicorn** in the container.
- **SQLite** stores shops in a single file persisted on a Docker named volume, so data survives restarts with zero database server to manage.
- **Ollama** runs the open-weight **`llama3.2:1b`** model entirely on the host. It is small enough to fit on a Raspberry Pi with 4 GB of memory, which is exactly the kind of cheap, always-on box a neighborhood group could afford. `ai.py` talks to it over HTTP (`POST /api/generate`, `stream: false`).

The model does two narrow jobs with short prompts to keep token counts low on modest hardware:

1. **Rank partners** — given a selected shop and a numbered list of *already-filtered* candidates, return the ordered ids of the best up to three, matched on segment complementarity and related target audience.
2. **Write a promo blurb** — given two shop names and segments, return one or two short English sentences promoting the collaboration.

**Graceful degradation is the headline design decision.** Every call into `ai.py` is wrapped in a cascade of error handling covering timeouts, connection failures, non-200 responses, and malformed JSON. Each failure routes to a local, deterministic heuristic:

- If ranking fails, the pre-filtered candidates are ordered heuristically (shared/related target audience, then name) and capped at three.
- If blurb generation fails, a template combines the two names, segments, and neighborhood into a usable sentence.

Both paths return the same shape to the routes, so the UI renders identically whether the text came from the model or the fallback. The practical result: on a slow or offline Pi, the app never shows an error page — registration, browsing, suggestions, and promos all keep working. The AI makes the output smarter; it is never a single point of failure.

## Why Does Open Innovation Matter?

Running an **open-weight model locally** instead of calling a closed, hosted API changed what this project could be:

- **Privacy by default.** Shop details and partnership ideas never leave the owner's own hardware. There is no third party logging who is pairing with whom.
- **It runs on a Raspberry Pi.** `llama3.2:1b` fits in 4 GB of memory, so a neighborhood association can self-host the whole thing on a sub-$100 box. A closed API would push the intelligence into someone else's cloud and someone else's pricing.
- **No per-call cost.** Suggestions and promo blurbs are generated as often as owners like, with zero marginal cost. For a free community tool, metered API calls would be a non-starter.
- **It works offline.** Flaky connectivity does not break it — the model is local, and even if the model itself is down, the heuristic fallbacks keep every feature usable.

Open weights plus a tiny footprint are what let a genuinely useful AI feature live on cheap, private, offline-capable hardware. That is the difference between a tool a neighborhood can actually own and one it merely rents.

## My First User

<!-- Optional. Remove if unused. -->

## Prize Categories

<!-- Optional. List applicable partner categories or remove this section. -->

---

### Run it on a Raspberry Pi (4 GB) with Docker

From the `desafio3/` directory:

```bash
# 1. Build and start the web + ollama services
docker compose up --build

# 2. In a second terminal, pull the model into the ollama service (one time; cached afterwards)
docker compose exec ollama ollama pull llama3.2:1b

# 3. Open the app
#    http://localhost:5000
```

The `ollama` service caches the pulled model on a named volume, and the SQLite database is persisted on its own named volume, so both survive container restarts. The app runs on port **5000**.
