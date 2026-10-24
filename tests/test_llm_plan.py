"""
python3 -m unittest tests/test_llm_plan.py      (from the project root; no network, no SDK needed)

The LLM path's safety lives in validate(): whatever the model says, only
real, extracted signs reach the player, and the corpus's negation trap is
flagged.
"""
import json
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
from backend import llm_plan  # noqa: E402

FAKE = {"signs": {
    "doctor": {"gloss": "DOCTOR", "kind": "plain", "keys": ["DOCTOR"], "clip": "1"},
    "who": {"gloss": "WHO", "kind": "plain", "keys": ["WHO"], "clip": "2"},
    "your": {"gloss": "YOUR", "kind": "plain", "keys": ["YOUR"], "clip": "3", "low": True},
    "later": {"gloss": "LATER", "kind": "plain", "keys": ["LATER"], "clip": None},
    "want-not-want": {"gloss": "WANT (NOT WANT)", "kind": "phrase", "keys": ["NOT WANT"], "clip": "4"},
    "open-door": {"gloss": "OPEN (DOOR)", "kind": "sense", "keys": ["OPEN"], "sense": "DOOR", "clip": "5"},
}, "keys": {}}


def step(kind, id="", text="", english="", confidence="high"):
    return {"kind": kind, "id": id, "text": text, "english": english, "confidence": confidence}


class Validate(unittest.TestCase):
    def test_good_plan_passes_through(self):
        line, rep = llm_plan.validate({"steps": [step("sign", "your", english="your"),
                                                 step("sign", "doctor", english="doctor"),
                                                 step("sign", "who", english="who")]}, FAKE)
        self.assertEqual(line, "your doctor who")
        self.assertEqual([r["status"] for r in rep], ["sign"] * 3)
        self.assertIn("low tracking", rep[0]["check"])

    def test_invented_id_is_never_played(self):
        line, rep = llm_plan.validate({"steps": [step("sign", "physician", english="physician")]}, FAKE)
        self.assertEqual(line, "fs:PHYSICIAN")
        self.assertEqual(rep[0]["status"], "rejected")
        self.assertIn("invented", rep[0]["problem"])

    def test_unextracted_sign_is_spelled_with_the_fix(self):
        line, rep = llm_plan.validate({"steps": [step("sign", "later", english="later")]}, FAKE)
        self.assertEqual(line, "fs:LATER")
        self.assertIn("add_sign.py --id later", rep[0]["problem"])

    def test_negation_trap_flagged(self):
        _, rep = llm_plan.validate({"steps": [step("sign", "want-not-want", english="want")]}, FAKE)
        self.assertIn("no negation", rep[0]["problem"])
        _, ok = llm_plan.validate({"steps": [step("sign", "want-not-want", english="don't want")]}, FAKE)
        self.assertNotIn("problem", ok[0])

    def test_sense_marked_for_review(self):
        _, rep = llm_plan.validate({"steps": [step("sign", "open-door", english="open")]}, FAKE)
        self.assertIn("specific sense", rep[0]["check"])

    def test_fingerspelling_letters_only(self):
        line, rep = llm_plan.validate({"steps": [step("fingerspell", text="Sabin-2", english="Sabin"),
                                                 step("fingerspell", text="42", english="42")]}, FAKE)
        self.assertEqual(line, "fs:SABIN")
        self.assertEqual(rep[1]["status"], "rejected")

    def test_ids_are_case_and_space_tolerant_but_exact(self):
        line, _ = llm_plan.validate({"steps": [step("sign", " Doctor ", english="doctor")]}, FAKE)
        self.assertEqual(line, "doctor")


class Request(unittest.TestCase):
    def test_lexicon_deterministic_and_complete(self):
        m = llm_plan.load_manifest()
        a, b = llm_plan.lexicon_text(m), llm_plan.lexicon_text(json.loads(json.dumps(m)))
        self.assertEqual(a, b)                                   # cache-stable prefix
        self.assertEqual(len(a.splitlines()), len(m["signs"]))
        self.assertIn("want-not-want\tWANT (NOT WANT)\t[means: not want]", a)

    def test_request_shape(self):
        r = llm_plan.build_request("hello", llm_plan.load_manifest())
        self.assertEqual(r["model"], "claude-opus-5-5")
        self.assertEqual(r["fallbacks"], "default")
        self.assertEqual(r["betas"], ["server-side-fallback-2026-07-01"])
        self.assertEqual(r["output_config"]["format"]["type"], "json_schema")
        self.assertEqual(r["system"][0]["cache_control"], {"type": "ephemeral"})
        self.assertEqual(r["messages"], [{"role": "user", "content": "hello"}])


if __name__ == "__main__":
    unittest.main()
