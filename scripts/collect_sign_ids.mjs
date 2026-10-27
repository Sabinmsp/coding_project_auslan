// Which signs does a list of English text need?  Used by
// build_dist.py --signs-from FILE to make a partial web build.
//
//   node scripts/collect_sign_ids.mjs FILE      -> JSON array of sign ids
//
// Every non-comment line of FILE is planned with the app's own planner, as
// a whole line and word by word; the result is every sign a plan would
// PLAY plus every alternative its menus would OFFER (so menu choices in the
// demo still work). Quick picks are always included.
import { readFileSync } from "node:fs";
import { plan } from "../frontend/src/planner.js";
import { Library } from "../frontend/src/library.js";
import { simplify } from "../frontend/src/summarize.js";

const root = new URL("../", import.meta.url);
const readJSON = rel => JSON.parse(readFileSync(new URL(rel, root)));
const lib = new Library({ manifest: readJSON("assets/signs/manifest.json"),
                          keywords: readJSON("assets/signs/keywords.json") });
const ids = new Set();
const lines = readFileSync(process.argv[2], "utf8").split("\n").map(l => l.trim()).filter(l => l && !l.startsWith("#"));
for (const line of lines) {
    // as written, as the summary's plain-English rules would show it, and word by word
    for (const text of [line, simplify(line), ...simplify(line).split(/\s+/), ...line.split(/\s+/)]) {
        for (const s of plan(text, lib).steps) {
            if (s.kind === "sign") ids.add(s.id);
            for (const o of s.options || []) ids.add(o.id);
        }
    }
}
for (const e of Object.values(readJSON("assets/signs.json"))) if (e.library) ids.add(e.library);
process.stdout.write(JSON.stringify([...ids].filter(id => lib.manifest.signs[id]).sort()));
