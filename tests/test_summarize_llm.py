"""
The optional AI summary endpoint, offline: request building, citation
mapping, error handling. No network, no API key needed.

    python3 -m unittest tests/test_summarize_llm.py
"""
import json
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from backend import summarize_llm as S  # noqa: E402

PAYLOAD = {"title": "Handbook", "excerpts": [
    {"text": "Your tuition fees are due on 31 March 2027.", "page": 2},
    {"text": "Late assignments lose 5% of the available marks for each day they are late.", "page": 1},
]}


class Request(unittest.TestCase):
    def test_excerpts_numbered_with_pages(self):
        req, ex = S.build_request(PAYLOAD, points=5)
        body = req["messages"][0]["content"]
        self.assertIn("[1] (page 2) Your tuition fees", body)
        self.assertIn("[2] (page 1) Late assignments", body)
        self.assertIn("5 most important points", req["system"])
        self.assertEqual(req["output_config"]["format"]["schema"], S.SCHEMA)

    def test_caps_and_cleaning(self):
        many = {"excerpts": [{"text": "x" * 5000, "page": i} for i in range(500)] + [{"text": "no page"}]}
        _, ex = S.build_request(many)
        self.assertEqual(len(ex), S.MAX_EXCERPTS)
        self.assertTrue(all(len(e["text"]) <= S.MAX_CHARS for e in ex))
        with self.assertRaises(S.SummaryError):
            S.build_request({"excerpts": []})


class Points(unittest.TestCase):
    def test_citations_become_pages(self):
        _, ex = S.build_request(PAYLOAD)
        pts = S.to_points({"points": [{"simple": "Pay your fees by 31 March 2027.", "excerpts": [1]},
                                      {"simple": "Late work loses 5% a day.", "excerpts": [2, 1]}]}, ex)
        self.assertEqual(pts[0]["pages"], [2])
        self.assertEqual(pts[1]["pages"], [1, 2])
        self.assertEqual(pts[0]["source"], "ai")

    def test_uncited_or_invented_citations_dropped(self):
        _, ex = S.build_request(PAYLOAD)
        pts = S.to_points({"points": [{"simple": "Made up.", "excerpts": []},
                                      {"simple": "Also made up.", "excerpts": [7]},
                                      {"simple": "", "excerpts": [1]}]}, ex)
        self.assertEqual(pts, [])


class Endpoint(unittest.TestCase):
    def test_bad_json(self):
        self.assertEqual(S.handle_post(b"{not json")[0], 400)

    def test_too_large(self):
        self.assertEqual(S.handle_post(b"x" * (S.MAX_BODY + 1))[0], 413)

    def test_no_excerpts(self):
        status, out = S.handle_post(b'{"excerpts": []}')
        self.assertEqual(status, 503)
        self.assertIn("excerpts", out["error"])

    def test_unavailable_without_sdk_or_key(self):
        with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": ""}):
            status, out = S.handle_post(json.dumps(PAYLOAD).encode())
        self.assertEqual(status, 503)
        self.assertIn("unavailable", out["error"])

    def test_success_path_with_a_stubbed_model(self):
        reply = {"points": [{"simple": "Pay your fees by 31 March 2027.", "excerpts": [1]}]}
        with mock.patch.object(S, "call_claude", return_value=reply):
            status, out = S.handle_post(json.dumps(PAYLOAD).encode())
        self.assertEqual(status, 200)
        self.assertEqual(out["points"][0]["pages"], [2])


if __name__ == "__main__":
    unittest.main()
