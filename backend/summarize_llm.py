"""
OPTIONAL AI step: rewrite a document's key excerpts as short, plain-English
points with Claude. The page works fully without it (frontend/src/summarize.js
is the offline summariser and the fallback).

Hierarchical by design: the browser extracts the PDF and picks the most
important sentences per chunk of pages (summarize.js); only those excerpts,
each tagged with its page, are sent here -- never the whole document. So a
200-page PDF costs about the same as a 10-page one.

What the model is trusted with, and what it is not:
  trusted  choosing the most useful points and rewording them simply
  not      facts. It may only use the numbered excerpts; every point must
           cite them; the server maps citations to real page numbers; and
           the browser re-checks every number, date, time, amount, email
           and link in each point against the cited pages (checkPoint),
           flagging any that are not there.

    python3 backend/summarize_llm.py excerpts.json          # call Claude, print points
    python3 backend/summarize_llm.py --show-prompt excerpts.json
    python3 backend/summarize_llm.py --response reply.json excerpts.json   # offline

excerpts.json: {"title": "...", "excerpts": [{"text": "...", "page": 3}, ...]}

Needs `pip install anthropic` and ANTHROPIC_API_KEY. Model: ANTHROPIC_MODEL
(default claude-opus-5-5).
"""
import argparse
import json
import os
import sys

MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-opus-5-5")
MAX_EXCERPTS = 80
MAX_CHARS = 600

SCHEMA = {
    "type": "object",
    "properties": {
        "points": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "simple": {"type": "string"},
                    "excerpts": {"type": "array", "items": {"type": "integer"}},
                },
                "required": ["simple", "excerpts"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["points"],
    "additionalProperties": False,
}

INSTRUCTIONS = """\
You help Deaf and hard-of-hearing students, many of whom use Auslan as their
first language, understand long English documents. You receive numbered
EXCERPTS from one document. Write the {n} most important points a student
must know, in plain English.

Rules:
- Use ONLY information in the excerpts. Never add facts, advice or details.
- Copy every number, date, time, amount, email address and link exactly as
  the excerpt writes it.
- Each point: one or two short sentences, at most 20 words each, common
  words, active voice ("You must ...").
- Prefer instructions, deadlines, requirements, costs and where to get help.
- Cite the excerpt number(s) each point comes from in "excerpts".
- Order the points as they appear in the document.
"""


class SummaryError(Exception):
    """A message safe to show the viewer."""


def clean_excerpts(payload):
    ex = payload.get("excerpts") if isinstance(payload, dict) else None
    if not isinstance(ex, list) or not ex:
        raise SummaryError("no excerpts to summarise")
    out = []
    for e in ex[:MAX_EXCERPTS]:
        text = str(e.get("text", ""))[:MAX_CHARS].strip()
        page = e.get("page")
        if text and isinstance(page, int):
            out.append({"text": text, "page": page})
    if not out:
        raise SummaryError("no usable excerpts")
    return out


def build_request(payload, points=10):
    ex = clean_excerpts(payload)
    body = "\n".join(f"[{i + 1}] (page {e['page']}) {e['text']}" for i, e in enumerate(ex))
    title = str(payload.get("title", ""))[:200]
    return {
        "model": MODEL,
        "max_tokens": 4000,
        "output_config": {"format": {"type": "json_schema", "schema": SCHEMA}},
        "system": INSTRUCTIONS.format(n=points),
        "messages": [{"role": "user", "content": f"Document: {title}\n\nEXCERPTS\n{body}"}],
    }, ex


def to_points(reply, ex):
    """Model reply -> points with real page numbers. Pure; no network.
    A point citing no valid excerpt is dropped, never trusted."""
    points = []
    for p in (reply or {}).get("points", []):
        ids = [i for i in p.get("excerpts", []) if isinstance(i, int) and 1 <= i <= len(ex)]
        simple = str(p.get("simple", "")).strip()
        if not ids or not simple:
            continue
        points.append({"simple": simple, "pages": sorted({ex[i - 1]["page"] for i in ids}),
                       "text": " ".join(ex[i - 1]["text"] for i in ids), "source": "ai"})
    return points


def call_claude(request):
    try:
        import anthropic
    except ImportError:
        raise SummaryError("AI summary unavailable on this server (anthropic SDK not installed)")
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise SummaryError("AI summary unavailable on this server (no ANTHROPIC_API_KEY)")
    client = anthropic.Anthropic()
    try:
        response = client.messages.create(**request)
    except anthropic.AuthenticationError:
        raise SummaryError("AI summary unavailable: the API key was rejected")
    except anthropic.RateLimitError:
        raise SummaryError("AI summary busy: rate limited, try again shortly")
    except anthropic.APIConnectionError:
        raise SummaryError("AI summary unavailable: could not reach the API")
    except anthropic.APIStatusError as e:
        raise SummaryError(f"AI summary failed: API error {e.status_code}")
    if response.stop_reason == "refusal":
        raise SummaryError("AI summary declined for this document")
    if response.stop_reason == "max_tokens":
        raise SummaryError("AI summary was cut off")
    text = next((b.text for b in response.content if b.type == "text"), "")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        raise SummaryError("AI summary returned an unreadable reply")


def summarize(payload, points=10):
    request, ex = build_request(payload, points)
    return {"model": request["model"], "points": to_points(call_claude(request), ex)}


MAX_BODY = 1_000_000


def handle_post(body):
    """POST /api/summarize body (bytes) -> (HTTP status, JSON-able dict).
    Shared by backend/serve.py and the Vercel function (backend/api_summarize.py)."""
    if len(body) > MAX_BODY:
        return 413, {"error": "request too large"}
    try:
        payload = json.loads(body or b"{}")
        n = int(payload.get("points", 10)) if isinstance(payload, dict) else 10
        return 200, summarize(payload, points=max(1, min(n, 20)))
    except (json.JSONDecodeError, ValueError):
        return 400, {"error": "request is not valid JSON"}
    except SummaryError as e:
        return 503, {"error": str(e)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("excerpts")
    ap.add_argument("--response", help="a saved model reply (JSON) to convert instead of calling")
    ap.add_argument("--show-prompt", action="store_true")
    args = ap.parse_args()
    with open(args.excerpts) as f:
        payload = json.load(f)
    request, ex = build_request(payload)
    if args.show_prompt:
        print(json.dumps(request, indent=2))
        return
    try:
        if args.response:
            with open(args.response) as f:
                reply = json.load(f)
        else:
            reply = call_claude(request)
    except SummaryError as e:
        sys.exit(str(e))
    print(json.dumps(to_points(reply, ex), indent=2))


if __name__ == "__main__":
    main()
