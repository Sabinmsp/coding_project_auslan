"""
English keyword -> sign index, from the dataset's own dictionary.

    python3 scripts/build_keywords.py

datasets/raw/Dictionary_Mapping.pt lists, for each of the 3,215 glosses,
the English words given for that sign: "remember, recall, memory" for
RECOLLECT; "able, can, could, may" for ABLE; "hello, hi" for HELLO. The
planner tries these AFTER the gloss names and their stems, so a word that
is not itself a gloss can still find its sign ("I can help" -> ABLE,
instead of fingerspelling or CAN (TIN)).

The same safety rules as the gloss names (scripts/ingest.py classify()):

  "want (not want)"          a keyword that negates or shifts its own
                             word is keyed ONLY by its meaning, NOT WANT --
                             never by "want"
  "learned (knowledgeable)"  a keyword with a sense needs evidence in the
                             sentence ("knowledgeable"), so "I learned"
                             still finds LEARN through its stem
  "train (steam train)"      a narrowing phrase: "steam train" finds it;
                             bare "train" only with evidence ("steam")
  "day" for DAY (THE NEXT DAY)
                             the dictionary lists the bare word for a sign
                             whose gloss shifts or negates it; the gloss
                             rule wins -- "day" becomes a sense needing
                             evidence ("next"), so it can never mean
                             "the next day" on its own

Keywords that are already one of the sign's own gloss keys are left out.

Output: assets/signs/keywords.json
  {"source": ..., "counts": {...},
   "keys": {"REMEMBER": [["recollect", "plain", null, 1, 8], ["prize", "plain", null, 6, 11]], ...}}
each entry: [sign id, kind, sense, position of this keyword in the sign's
list, length of the list]. The lists are loose -- NO WAY (REJECT) lists
"hi" and "hello" -- but the position carries the signal: "remember" is
RECOLLECT's 2nd keyword and PRIZE's 7th. The planner uses it to rank signs
that share a keyword, and marks any such choice for review.

The .pt file is read with an unpickler that refuses every class: it holds
only plain dicts and strings, so nothing in it can run code.
"""
import io
import json
import pickle
import sys
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from backend import paths  # noqa: E402
from ingest import classify, norm_key  # noqa: E402


class PlainDataOnly(pickle.Unpickler):
    def find_class(self, module, name):
        raise pickle.UnpicklingError(f"refusing to construct {module}.{name}")


def load_dictionary(path):
    with zipfile.ZipFile(path) as z:
        name = next(n for n in z.namelist() if n.endswith("data.pkl"))
        return PlainDataOnly(io.BytesIO(z.read(name)), encoding="latin1").load()


def main():
    catalog = json.loads(paths.CATALOG.read_text())
    gloss2sid = {s["gloss"]: sid for sid, s in catalog["signs"].items()}
    dictionary = load_dictionary(paths.DICTIONARY)["gloss2id"]

    keys = defaultdict(list)
    kinds = Counter()
    skipped_own, unknown = 0, []
    for gloss, entry in dictionary.items():
        sid = gloss2sid.get(gloss)
        if sid is None:
            unknown.append(gloss)
            continue
        own = set(catalog["signs"][sid]["keys"])
        sign = catalog["signs"][sid]
        # a gloss that negates / time-shifts its own word (WANT (NOT WANT),
        # DAY (THE NEXT DAY)): ingest keys it only by its meaning
        shifted = sign["kind"] == "phrase" and len(sign["keys"]) == 1
        listed = [k.strip() for k in entry["Keywords"].split(",") if k.strip()]
        for pos, raw in enumerate(listed):
            kind, kkeys, head, sense = classify(raw)
            for n, key in enumerate(kkeys):
                if not key or key in own:
                    skipped_own += 1
                    continue
                # keys[0] states the keyword's meaning; a later key (a bare head
                # word of a narrowing phrase) is only a sense of it
                if shifted and key == sign["head"]:
                    e = [sid, "sense", sign["keys"][0], pos, len(listed)]
                elif kind == "plain" or (kind == "phrase" and n == 0):
                    e = [sid, "plain", None, pos, len(listed)]
                elif kind == "plural":
                    e = [sid, "plural", sense, pos, len(listed)]
                else:
                    e = [sid, "sense", sense, pos, len(listed)]
                if not any(x[:3] == e[:3] for x in keys[key]):
                    keys[key].append(e)
                    kinds[e[1]] += 1
    out = {"source": paths.DICTIONARY.name,
           "counts": {"keys": len(keys), "entries": sum(len(v) for v in keys.values()),
                      **kinds, "ambiguous_keys": sum(1 for v in keys.values()
                                                     if sum(e[1] == "plain" for e in v) > 1)},
           "keys": dict(sorted(keys.items()))}
    paths.KEYWORDS.write_text(json.dumps(out, separators=(",", ":")))
    print(f"{len(keys)} keyword keys ({out['counts']}) -> {paths.KEYWORDS.relative_to(paths.ROOT)}")
    print(f"  keywords already a gloss key of their own sign (left out): {skipped_own}")
    if unknown:
        print(f"  glosses not in the catalog: {len(unknown)}")


if __name__ == "__main__":
    main()
