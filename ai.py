"""Ollama AI layer for the Neighbor Partner app.

This module is the client for the locally hosted Ollama model. It
exposes ``suggest_partners`` to rank pre-filtered candidate shops and
``generate_promo`` to write a short promotional blurb for a shop pair.
Both functions use short prompts, a bounded timeout, and local
heuristic fallbacks so they always return a usable value and never
raise, keeping the app operable when the AI service is slow or down.
"""

import os
import re

import requests

# Configuration via environment variables (see design / docker-compose).
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://ollama:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2:1b")

# HTTP timeout for a single generate call, in seconds.
_REQUEST_TIMEOUT = 30

# Maximum number of partner suggestions returned.
_MAX_SUGGESTIONS = 3

# Maximum length of a generated promo blurb, in characters.
_MAX_PROMO_LENGTH = 300


def _generate(prompt):
    """POST a prompt to the Ollama generate endpoint and return its text.

    Returns the model's ``response`` string on success, or ``None`` on any
    failure (timeout, connection error, other request error, non-200
    status, or malformed/missing JSON). This helper never raises.
    """
    try:
        resp = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False},
            timeout=_REQUEST_TIMEOUT,
        )
    except requests.exceptions.Timeout:
        return None
    except requests.exceptions.ConnectionError:
        return None
    except requests.exceptions.RequestException:
        return None

    if resp.status_code != 200:
        return None

    try:
        data = resp.json()
    except ValueError:
        # Malformed or missing JSON body.
        return None

    if not isinstance(data, dict):
        return None

    text = data.get("response")
    if not isinstance(text, str):
        return None

    return text


def _normalize_audience(value):
    """Return a lowercase, trimmed target-audience string for comparison."""
    return (value or "").strip().lower()


def _audience_match_score(shop, candidate):
    """Score how related two shops' target audiences are.

    2 = identical audience, 1 = overlapping words, 0 = unrelated. Used to
    order candidates deterministically in the heuristic fallback.
    """
    a = _normalize_audience(shop["target_audience"])
    b = _normalize_audience(candidate["target_audience"])
    if not a or not b:
        return 0
    if a == b:
        return 2
    a_words = set(a.split())
    b_words = set(b.split())
    if a_words & b_words:
        return 1
    return 0


def _heuristic_order(shop, candidates):
    """Deterministically order candidates for the suggestions fallback.

    Candidates are already pre-filtered (same neighborhood, different
    segment). Order by shared/related target-audience match (descending),
    then by name, and cap at three.
    """
    ordered = sorted(
        candidates,
        key=lambda c: (-_audience_match_score(shop, c), (c["name"] or "").lower()),
    )
    return ordered[:_MAX_SUGGESTIONS]


def _build_suggest_prompt(shop, candidates):
    """Build the short partner-ranking prompt for the model."""
    lines = [
        "You help a local shop find complementary, non-competing partners.",
        "",
        "Selected shop:",
        f"- name: {shop['name']}",
        f"- segment: {shop['segment']}",
        f"- target audience: {shop['target_audience']}",
        "",
        "Candidate partners (same neighborhood, different segment):",
    ]
    for index, candidate in enumerate(candidates, start=1):
        lines.append(
            f"{index}. id={candidate['id']} "
            f"name={candidate['name']} "
            f"segment={candidate['segment']} "
            f"target_audience={candidate['target_audience']}"
        )
    lines.extend(
        [
            "",
            "Pick up to three best partners, matched on segment "
            "complementarity and related target audience.",
            "Reply with only the chosen ids in order, separated by commas, "
            "best first. Example: 3, 1",
        ]
    )
    return "\n".join(lines)


def _parse_ids(text, valid_ids):
    """Extract candidate ids from the model's reply, preserving order.

    Only ids present in ``valid_ids`` are kept, duplicates are dropped,
    and the result is capped at three.
    """
    result = []
    seen = set()
    for token in re.findall(r"\d+", text or ""):
        try:
            candidate_id = int(token)
        except ValueError:
            continue
        if candidate_id in valid_ids and candidate_id not in seen:
            result.append(candidate_id)
            seen.add(candidate_id)
        if len(result) >= _MAX_SUGGESTIONS:
            break
    return result


def suggest_partners(shop, candidates):
    """Return up to three ranked partner shops for ``shop``.

    ``candidates`` are already pre-filtered to the same neighborhood and a
    different segment. The model is asked to order them by segment
    complementarity and related target audience; its reply is parsed for
    known candidate ids. On any failure or unusable output, a deterministic
    heuristic ordering is returned instead. Never raises.
    """
    candidates = list(candidates or [])
    if not candidates:
        return []

    by_id = {c["id"]: c for c in candidates}

    text = _generate(_build_suggest_prompt(shop, candidates))
    if text is not None:
        ordered_ids = _parse_ids(text, set(by_id.keys()))
        if ordered_ids:
            return [by_id[i] for i in ordered_ids]

    # Fallback: deterministic heuristic ordering.
    return _heuristic_order(shop, candidates)


def _fallback_promo(shop_a, shop_b):
    """Return the English template blurb used when the model is unavailable."""
    return (
        f"Visit {shop_a['name']} ({shop_a['segment']}) and "
        f"{shop_b['name']} ({shop_b['segment']}) — two neighbors in "
        f"{shop_a['neighborhood']} teaming up to serve you better."
    )


def generate_promo(shop_a, shop_b):
    """Return a short promotional blurb for the pair ``shop_a`` + ``shop_b``.

    The model is asked for one or two short English sentences promoting the
    collaboration; the reply is trimmed and length-capped. On any failure or
    empty output, an English template blurb is returned. Never raises.
    """
    prompt = (
        "Write one or two short English sentences promoting a co-promotion "
        "between two neighboring shops.\n"
        f"Shop A: {shop_a['name']} (segment: {shop_a['segment']}).\n"
        f"Shop B: {shop_b['name']} (segment: {shop_b['segment']}).\n"
        "Keep it friendly and concise. Reply with only the promotional text."
    )

    text = _generate(prompt)
    if text is not None:
        text = text.strip()
        if text:
            if len(text) > _MAX_PROMO_LENGTH:
                text = text[:_MAX_PROMO_LENGTH].rstrip()
            return text

    # Fallback: English template blurb.
    return _fallback_promo(shop_a, shop_b)
