#!/bin/sh
# Finish the sign library after a full extraction run:
#
#   1. wait for any running scripts/build_library.py to end
#   2. primary pass again -- resumes anything left undone (a no-op if complete)
#   3. validate every sign
#   4. rescue: extract the SECOND recording of every flagged sign
#      (review / unreliable / failed); the manifest keeps the better take
#   5. validate again
#   6. rebuild the deployable site (dist/)
#   7. write datasets/processed/final_status.txt: counts, and the signs
#      that are still unreliable -- those need a new recording
#
#   sh scripts/finish_library.sh
#   caffeinate -i sh scripts/finish_library.sh     # keep the Mac awake
set -e
cd "$(dirname "$0")/.."
PY=$(python3 -c "import sys; sys.path.insert(0, '.'); from backend import paths; print(paths.python_with_mediapipe())")
STATUS=datasets/processed/final_status.txt
rm -f "$STATUS"

stamp() { echo "== $(date '+%H:%M') $*"; }

stamp "waiting for a running extraction to finish"
while pgrep -f "scripts/build_library.py" > /dev/null; do sleep 60; done

stamp "primary pass (resumes anything not yet extracted)"
"$PY" scripts/build_library.py --workers 4

stamp "validate (1/2)"
python3 scripts/validate_signs.py

stamp "rescue: second recording for every flagged sign"
"$PY" scripts/build_library.py --takes rescue --rescue-below 0 --workers 4

stamp "validate (2/2)"
python3 scripts/validate_signs.py

stamp "deployable site"
python3 scripts/build_dist.py

stamp "final status -> $STATUS"
python3 - "$STATUS" <<'PY'
import collections, json, sys
from pathlib import Path
sys.path.insert(0, ".")
from backend import paths
m = json.loads(paths.MANIFEST.read_text())
c = json.loads(paths.CATALOG.read_text())
log = {}
for line in paths.EXTRACT_LOG.read_text().splitlines():
    r = json.loads(line); log[r["clip"]] = r
avail = {i: s for i, s in m["signs"].items() if s["clip"]}
status = collections.Counter(s.get("status", "ok") for s in avail.values())
second = sum(1 for i, s in avail.items() if s["clip"] != c["signs"][i]["takes"][0]["clip"])
unreliable = sorted((i, s) for i, s in avail.items() if s.get("status") == "unreliable")
missing = sorted(i for i, s in m["signs"].items() if not s["clip"])
out = [f"library: {len(avail)} of {len(m['signs'])} signs playable"
       + (f"; {len(missing)} not extracted: {', '.join(missing[:20])}" if missing else ""),
       f"  ok {status['ok']}   review {status['review']}   unreliable {status['unreliable']}",
       f"  {second} signs use their second recording (it validated better)",
       f"  extraction failures: {sum(1 for r in log.values() if not r['ok'])}",
       "",
       f"STILL UNRELIABLE AFTER BOTH RECORDINGS ({len(unreliable)}) -- need a new recording;",
       "a typed sentence fingerspells these, a quick pick shows the warning:"]
out += [f"  {i:28} {s['gloss']:32} {', '.join(s.get('flags', []))}" for i, s in unreliable]
Path(sys.argv[1]).write_text("\n".join(out) + "\n")
print("\n".join(out[:4]))
PY
stamp "done"
