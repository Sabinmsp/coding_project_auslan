"""
OPTIONAL: ask Claude for an Auslan-ordered sign plan, then validate every
step against the library before anything can play.

    python3 backend/llm_plan.py "Hello, my name is Sabin."
    python3 backend/llm_plan.py --show-prompt "..."          # print the request, send nothing
    python3 backend/llm_plan.py --response saved.json "..."  # validate a saved reply offline

Needs `pip install anthropic` and credentials (ANTHROPIC_API_KEY, or an
`ant auth login` profile). The rule-based planner in frontend/src/planner.js needs
neither and is what the page uses by default.

What the model is trusted with, and what it is not:

  trusted   choosing which listed signs express the sentence, in what
            order -- including synonyms the rule planner cannot find
            ("physician" -> DOCTOR) and Auslan ordering it does not model.
  not       inventing signs. The model only ever names ids from the
            lexicon it is given; validate() then checks every id against
            the manifest anyway. An unknown id, or a sign not extracted
            yet, becomes fingerspelling, and the report says so.

Output is the same gloss line the page's plan editor accepts, plus a link
that opens the page playing it. It is LLM-proposed and NOT verified by an
Auslan user -- it goes through the same human review path as any plan.
"""
import argparse
import json
import re
import sys
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.paths import MANIFEST  # noqa: E402
MODEL = "claude-opus-5-5"
NEGATORS = re.compile(r"\b(not|no|never|nothing|none|don't|doesn't|didn't|can't|cannot|"
                      r"won't|isn't|aren't|wasn't|weren't|shouldn't|haven't|hasn't|n't)\b", re.I)

PLAN_SCHEMA = {
    "type": "object",
    "properties": {
        "steps": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "kind": {"type": "string", "enum": ["sign", "fingerspell"]},
                    "id": {"type": "string"},
                    "text": {"type": "string"},
                    "english": {"type": "string"},
                    "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
                },
                "required": ["kind", "id", "text", "english", "confidence"],
                "additionalProperties": False,
            },
        },
        "non_manual": {"type": "string"},
        "notes": {"type": "string"},
    },
    "required": ["steps", "non_manual", "notes"],
    "additionalProperties": False,
}

INSTRUCTIONS = """\
You plan sign sequences for an Auslan (Australian Sign Language) prototype.
A 2D figure replays recorded signs, one per step, so a plan can only use
signs from the LEXICON below. Each lexicon line is: id, then the corpus
gloss. A gloss in parentheses is either a specific sense -- OPEN (DOOR) is
opening a door -- or, when marked [means: ...], the sign's whole meaning:
WANT (NOT WANT) [means: not want] is "don't want" and must never be used
for "want".

Produce the sequence a fluent signer would most plausibly use:
- Use only ids that appear in the LEXICON, copied exactly. Never invent one.
- If no listed sign fits a word or name, fingerspell it (kind
  "fingerspell", letters only in "text"). Names are fingerspelled.
- Choose a specific sense only when it matches the meaning in context.
- Apply Auslan conventions where you are confident of them: no articles or
  copula, time expressions first, topic before comment, a wh-question word
  usually at the end. Do not force a rule you are unsure of.
- "english" says which words of the input each step expresses;
  "confidence" is your confidence that the step is the right sign for
  that meaning in Auslan.
- The figure cannot add facial expression or head movement. Describe the
  non-manual features a signer would add (brow position, headshake,
  mouthing) in "non_manual", so a reviewer can see what is missing.
- Use "notes" for anything a reviewer should check.

LEXICON
"""


def load_manifest(path=MANIFEST):
    return json.loads(Path(path).read_text())


def lexicon_text(manifest):
    """Deterministic (sorted) so the cached prompt prefix stays byte-identical."""
    lines = []
    for sid in sorted(manifest["signs"]):
        s = manifest["signs"][sid]
        line = f"{sid}\t{s['gloss']}"
        if s["kind"] == "phrase":
            line += f"\t[means: {s['keys'][0].lower()}]"
        lines.append(line)
    return "\n".join(lines)


def build_request(sentence, manifest):
    return {
        "model": MODEL,
        "max_tokens": 16000,
        "betas": ["server-side-fallback-2026-07-01"],
        "fallbacks": "default",
        "output_config": {"effort": "high",
                          "format": {"type": "json_schema", "schema": PLAN_SCHEMA}},
        "system": [{"type": "text", "text": INSTRUCTIONS + lexicon_text(manifest),
                    "cache_control": {"type": "ephemeral"}}],
        "messages": [{"role": "user", "content": sentence}],
    }


def letters(text):
    return re.sub(r"[^A-Z]", "", text.upper())


def validate(plan, manifest):
    """Model output -> (gloss line, per-step report). Pure; no network.

    Every sign id is checked against the manifest. Anything that cannot be
    played as the sign it claims to be is fingerspelled instead, and the
    reason is recorded -- never silently dropped, never trusted."""
    tokens, report = [], []
    signs = manifest["signs"]
    for i, step in enumerate(plan.get("steps", [])):
        english = (step.get("english") or "").strip()
        entry = {"n": i, "english": english, "confidence": step.get("confidence")}
        if step.get("kind") == "sign":
            sid = (step.get("id") or "").strip().lower()
            s = signs.get(sid)
            fallback = letters(english) or letters(sid)
            if s is None:
                entry.update(status="rejected", problem=f"'{sid}' is not in the lexicon "
                             f"(invented id) -- fingerspelled")
                if fallback:
                    tokens.append(f"fs:{fallback}")
            elif not s["clip"]:
                entry.update(status="pending", id=sid, gloss=s["gloss"],
                             problem=f"{s['gloss']} is not extracted yet -- fingerspelled; "
                                     f"python3 scripts/add_sign.py --id {sid}")
                if fallback:
                    tokens.append(f"fs:{fallback}")
            else:
                entry.update(status="sign", id=sid, gloss=s["gloss"])
                tokens.append(sid)
                # the trap this corpus sets: a negated sign for a positive word
                if s["kind"] == "phrase" and NEGATORS.search(s["keys"][0]) \
                        and not NEGATORS.search(english):
                    entry["problem"] = (f"{s['gloss']} means '{s['keys'][0].lower()}' "
                                        f"but the English '{english}' has no negation -- check")
                elif s["kind"] in ("sense", "plural"):
                    entry["check"] = f"specific sense: {s['gloss']}"
                if s.get("low"):
                    entry["check"] = (entry.get("check", "") + "; " if entry.get("check") else "") \
                        + "low tracking quality in source clip"
        elif step.get("kind") == "fingerspell":
            spelled = letters(step.get("text") or "") or letters(english)
            if spelled:
                entry.update(status="spell", text=spelled)
                tokens.append(f"fs:{spelled}")
            else:
                entry.update(status="rejected", problem="fingerspelling with no letters -- dropped")
        else:
            entry.update(status="rejected", problem=f"unknown step kind {step.get('kind')!r}")
        report.append(entry)
    return " ".join(tokens), report


def call_claude(request):
    try:
        import anthropic
    except ImportError:
        sys.exit("The anthropic SDK is not installed. In the project's venv:\n"
                 "    <venv>/bin/pip install anthropic   (see requirements.txt)\n"
                 "(the rule-based planner on the page needs none of this)")
    client = anthropic.Anthropic()
    try:
        response = client.beta.messages.create(**request)
    except anthropic.AuthenticationError:
        sys.exit("No valid credentials: set ANTHROPIC_API_KEY, or run `ant auth login`.")
    except anthropic.PermissionDeniedError as e:
        sys.exit(f"Permission denied: {e.message}")
    except anthropic.RateLimitError:
        sys.exit("Rate limited -- try again shortly.")
    except anthropic.APIStatusError as e:
        sys.exit(f"API error {e.status_code}: {e.message}")
    except anthropic.APIConnectionError:
        sys.exit("Could not reach the API -- check the network connection.")

    if response.stop_reason == "refusal":
        detail = response.stop_details
        sys.exit(f"The request was declined ({detail.category if detail else 'no category'}). "
                 "Use the rule-based planner on the page instead.")
    if response.stop_reason == "max_tokens":
        sys.exit("The reply was cut off at max_tokens -- the plan is incomplete.")
    text = next(b.text for b in response.content if b.type == "text")
    usage = response.usage
    print(f"[{response.model}: {usage.input_tokens} input, "
          f"{getattr(usage, 'cache_read_input_tokens', 0) or 0} cached, "
          f"{usage.output_tokens} output tokens]", file=sys.stderr)
    return json.loads(text)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("sentence")
    ap.add_argument("--response", help="validate a saved model reply (JSON) instead of calling")
    ap.add_argument("--show-prompt", action="store_true")
    ap.add_argument("--base-url", default="http://localhost:8001/")
    args = ap.parse_args()

    manifest = load_manifest()
    request = build_request(args.sentence, manifest)
    if args.show_prompt:
        shown = dict(request, system=[dict(request["system"][0],
                     text=request["system"][0]["text"][:1800] + "\n... "
                     f"({len(manifest['signs'])} lexicon lines)")])
        print(json.dumps(shown, indent=2))
        return
    plan = (json.loads(Path(args.response).read_text()) if args.response
            else call_claude(request))
    line, report = validate(plan, manifest)

    print("LLM-proposed plan -- NOT verified by an Auslan user\n")
    for r in report:
        what = r.get("gloss") or (f"fs:{r['text']}" if r.get("text") else "")
        flag = r.get("problem") or r.get("check") or ""
        print(f"  {r['status']:9} {what:28} <- {r['english']!r:22} "
              f"{r.get('confidence') or ''}  {flag}")
    if plan.get("non_manual"):
        print(f"\nnon-manual (not shown by the figure): {plan['non_manual']}")
    if plan.get("notes"):
        print(f"notes: {plan['notes']}")
    print(f"\ngloss line:  {line}")
    print(f"play it:     {args.base_url}?gloss={urllib.parse.quote(line)}")


if __name__ == "__main__":
    main()
