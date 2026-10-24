"""
../.venv-1/bin/python -m unittest tests/test_pipeline.py   (from the project root)

Catalog rules, manifest integrity, and that the compact library format is
lossless against a fresh extraction of the same clip (~15s: it re-runs
MediaPipe on one clip).
"""
import json
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
from backend import paths  # noqa: E402
CATALOG = json.loads(paths.CATALOG.read_text())
MANIFEST = json.loads(paths.MANIFEST.read_text())


class Catalog(unittest.TestCase):
    def test_every_gloss_once_ids_unique(self):
        labels = json.loads(paths.LABELS.read_text())
        self.assertEqual(sorted({s["gloss"] for s in CATALOG["signs"].values()}),
                         sorted(set(labels.values())))
        self.assertEqual(len(CATALOG["signs"]), len(set(labels.values())))

    def test_every_take_has_a_file(self):
        for s in CATALOG["signs"].values():
            for t in s["takes"]:
                self.assertTrue((paths.VIDEO_ROOT / t["path"]).exists(), t["path"])

    def test_negated_glosses_never_keyed_by_head_word(self):
        keys = CATALOG["keys"]
        for word in ("WANT", "GOOD", "KNOW", "LIKE", "BELIEVE"):
            for sid in keys.get(word, []):
                self.assertNotIn("NOT", CATALOG["signs"][sid]["gloss"].split("(")[-1],
                                 f"{word} -> {sid}")
        self.assertEqual(keys["NOT WANT"], ["want-not-want"])
        self.assertEqual(keys["NO GOOD"], ["good-no-good"])

    def test_senses_keyed_by_head_word(self):
        self.assertIn("open-door", CATALOG["keys"]["OPEN"])
        self.assertEqual(CATALOG["signs"]["open-door"]["sense"], "DOOR")


class Manifest(unittest.TestCase):
    def test_available_means_files_exist(self):
        for sid, s in MANIFEST["signs"].items():
            if s["clip"]:
                self.assertTrue((paths.SIGN_MOTION / f"{s['clip']}.json").exists(), sid)
                self.assertTrue((paths.SIGN_VIDEOS / f"{s['clip']}.mp4").exists(), sid)

    def test_counts_match(self):
        c = MANIFEST["counts"]
        self.assertEqual(c["signs"], len(MANIFEST["signs"]))
        self.assertEqual(c["available"], sum(1 for s in MANIFEST["signs"].values() if s["clip"]))


class CompactFormat(unittest.TestCase):
    CLIP = "20062"

    @classmethod
    def setUpClass(cls):
        from backend import extract_motion
        cls.em = extract_motion
        cls.fresh, _ = extract_motion.extract(paths.RGB / f"{cls.CLIP}_kf_rgb.mp4",
                                              face=True, log=lambda *a, **k: None)
        cls.stored = json.loads((paths.SIGN_MOTION / f"{cls.CLIP}.json").read_text())

    def close(self, flat, points):
        s = self.stored["scale"]
        self.assertEqual(len(flat), 2 * len(points))
        for i, p in enumerate(points):
            self.assertLessEqual(abs(flat[2 * i] / s - p["x"]), 0.5 / s + 1e-12)
            self.assertLessEqual(abs(flat[2 * i + 1] / s - p["y"]), 0.5 / s + 1e-12)

    def test_lossless_to_quantisation(self):
        if self.stored.get("xv", 2) != self.em.EXTRACTOR_VERSION:
            self.skipTest(f"clip {self.CLIP} was stored by an older extractor; re-extract to compare")
        st, fr = self.stored, self.fresh["frames"]
        self.assertEqual(st["n"], len(fr))
        aspect = self.fresh["width"] / self.fresh["height"]
        for i, f in enumerate(fr):
            self.assertEqual(st["pose"][i] == 0, f["pose"] is None)
            if f["pose"]:
                self.close(st["pose"][i], f["pose"])
            if f.get("face"):
                self.close(st["face"][i], f["face"])
            for side in ("left", "right"):
                key = f"{side}_hand"
                possible = bool(f[key]) and self.em.is_possible(f[key], side, aspect)
                # stored iff geometrically possible -- impossible hands are dropped
                self.assertEqual(st[key][i] != 0, possible, f"{key} frame {i}")
                if possible:
                    self.close(st[key][i], f[key])


def _pose(lw, rw):
    """A 33-point pose, aspect 1: shoulders 0.2 apart, wrists where given."""
    p = [{"x": 0.5, "y": 0.5, "visibility": 1.0} for _ in range(33)]
    p[11], p[12] = {"x": 0.6, "y": 0.4, "visibility": 1.0}, {"x": 0.4, "y": 0.4, "visibility": 1.0}
    p[23], p[24] = {"x": 0.58, "y": 0.9, "visibility": 1.0}, {"x": 0.42, "y": 0.9, "visibility": 1.0}
    p[15], p[16] = {"x": lw[0], "y": lw[1], "visibility": 1.0}, {"x": rw[0], "y": rw[1], "visibility": 1.0}
    return p


def _hand(x, y, dx):
    """21 points in a line from the wrist (x, y), pointing along dx."""
    return [{"x": x + k * dx, "y": y - k * 0.004, "z": 0.0} for k in range(21)]


class Ownership(unittest.TestCase):
    """A hand is only ever stored in the slot of the arm it is attached to."""

    @classmethod
    def setUpClass(cls):
        from backend import extract_motion
        cls.em = extract_motion

    def frame(self, pose, left, right):
        return {"pose": pose, "left_hand": left, "right_hand": right,
                "left_hand_source": "holistic" if left else None,
                "right_hand_source": "holistic" if right else None}

    def test_hand_in_the_wrong_slot_is_dropped(self):
        pose = _pose((0.62, 0.7), (0.38, 0.7))
        f = self.frame(pose, _hand(0.62, 0.7, 0.01), _hand(0.62, 0.7, -0.01))   # "right" hand at the LEFT wrist
        dropped = self.em.resolve_ownership(f, 1.0)
        self.assertIsNone(f["right_hand"])
        self.assertIsNotNone(f["left_hand"])
        self.assertEqual(dropped["wrong_slot"], 1)

    def test_same_hand_in_both_slots_keeps_one(self):
        pose = _pose((0.51, 0.7), (0.49, 0.7))                                   # wrists touching
        h = _hand(0.5, 0.7, 0.01)
        f = self.frame(pose, h, [dict(p) for p in h])
        dropped = self.em.resolve_ownership(f, 1.0)
        self.assertEqual(dropped["duplicate"], 1)
        self.assertEqual(sum(x is not None for x in (f["left_hand"], f["right_hand"])), 1)

    def test_touching_hands_are_both_kept(self):
        pose = _pose((0.51, 0.7), (0.49, 0.7))
        left, right = _hand(0.53, 0.7, 0.01), _hand(0.505, 0.7, -0.01)          # right sits nearer the left wrist
        f = self.frame(pose, left, right)
        self.assertEqual(self.em.resolve_ownership(f, 1.0), {"wrong_slot": 0, "duplicate": 0})
        self.assertIs(f["left_hand"], left)
        self.assertIs(f["right_hand"], right)


class Validation(unittest.TestCase):
    """The validator catches the PAY bug in the data that had it, and the
    fixed extraction of the same clip is clean."""

    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, str(HERE / "scripts"))
        import validate_signs
        cls.v = validate_signs

    def test_old_pay_flagged_unreliable(self):
        old = json.loads((HERE / "tests" / "fixtures" / "pay_26475_extractor_v2.json").read_text())
        r = self.v.analyse(old)
        self.assertEqual(r["status"], "unreliable")
        self.assertGreaterEqual(r["wrong_slot"], 10)
        self.assertGreaterEqual(r["duplicate"], 10)

    def test_fixed_pay_is_clean(self):
        clip = MANIFEST["signs"]["pay"]["clip"]
        m = json.loads((paths.SIGN_MOTION / f"{clip}.json").read_text())
        if m.get("xv", 2) < 4:
            self.skipTest("PAY not yet re-extracted by the fixed extractor")
        r = self.v.analyse(m)
        self.assertEqual((r["wrong_slot"], r["duplicate"]), (0, 0))
        self.assertEqual(r["status"], "ok")


class Keywords(unittest.TestCase):
    """The dictionary keyword index (scripts/build_keywords.py) keeps the
    gloss names' safety rules."""

    @classmethod
    def setUpClass(cls):
        cls.kw = json.loads(paths.KEYWORDS.read_text())["keys"]

    def test_negated_signs_never_keyed_by_their_bare_word(self):
        blocked = [(sid, s) for sid, s in CATALOG["signs"].items()
                   if s["kind"] == "phrase" and len(s["keys"]) == 1]      # WANT (NOT WANT) ...
        self.assertGreaterEqual(len(blocked), 31)
        for sid, s in blocked:
            for entry in self.kw.get(s["head"], []):
                self.assertFalse(entry[0] == sid and entry[1] == "plain", f"{s['head']} -> {sid}")
        self.assertNotIn("WANT", self.kw)

    def test_sense_keywords_need_evidence(self):
        # "learned (knowledgeable)" must not make "learned" mean ENLIGHTENMENT
        self.assertEqual({e[1] for e in self.kw["LEARNED"] if e[0] == "enlightenment"}, {"sense"})

    def test_examples(self):
        self.assertIn(["able", "plain"], [e[:2] for e in self.kw["CAN"]])
        self.assertIn(["recollect", "plain"], [e[:2] for e in self.kw["REMEMBER"]])
        self.assertIn(["be-not-be", "plain"], [e[:2] for e in self.kw["HAVE NONE"]])


if __name__ == "__main__":
    unittest.main()
