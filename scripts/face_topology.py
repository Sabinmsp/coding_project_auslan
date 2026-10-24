"""
Writes assets/signs/face_topology.json: how to draw the 128 face points that
build_library.py stores per frame (extract_motion.FACE_KEEP, in that
order). Edges are given as POSITIONS into that stored list, not mesh ids,
so the player needs no knowledge of the 468-point mesh. The face oval is
also given as one ordered loop, so it can be filled as a head shape.

    ../.venv-1/bin/python scripts/face_topology.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend import paths  # noqa: E402
from backend import extract_motion as em  # noqa: E402

pos = {mesh_id: i for i, mesh_id in enumerate(em.FACE_KEEP)}
parts = {name: [[pos[a], pos[b]] for a, b in sorted(edges)]
         for name, edges in em.FACE_PARTS.items()}

# walk the oval's edges into one cycle
adj = {}
for a, b in em.FACE_PARTS["face_oval"]:
    adj.setdefault(a, []).append(b)
    adj.setdefault(b, []).append(a)
start = min(adj)
loop, prev, cur = [start], None, start
while True:
    nxt = [n for n in adj[cur] if n != prev][0]
    if nxt == start:
        break
    loop.append(nxt)
    prev, cur = cur, nxt
assert len(loop) == len(adj), "face oval is not a single cycle"

out = paths.FACE_TOPOLOGY
out.write_text(json.dumps({"indices": em.FACE_KEEP, "parts": parts,
                           "oval_loop": [pos[i] for i in loop]}))
print(f"{out.name}: {len(em.FACE_KEEP)} points, "
      + ", ".join(f"{k} {len(v)}" for k, v in parts.items()) + f", oval loop {len(loop)}")
