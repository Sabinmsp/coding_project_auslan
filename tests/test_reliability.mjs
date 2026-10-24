// node --test tests/
// Reliability: failed extraction, missing files, unreliable-sign filtering
// across the whole real library, and playback continuity on real clips.
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { plan, fromGlossLine } from "../frontend/src/planner.js";
import { Library, decodeMotion, normalizeMotion, activeSpan } from "../frontend/src/library.js";
import { buildTimeline, sample } from "../frontend/src/timeline.js";

const root = new URL("../", import.meta.url);
const readJSON = rel => JSON.parse(readFileSync(new URL(rel, root)));
const manifest = readJSON("assets/signs/manifest.json");
const keywords = readJSON("assets/signs/keywords.json");
const noFetch = async () => { throw new Error("no fetch in tests"); };

test("failed extraction: the sign is never planned as a sign", () => {
    const lex = new Library({ fetchJSON: noFetch, manifest: {
        signs: { doctor: { gloss: "DOCTOR", kind: "plain", keys: ["DOCTOR"], clip: null, failed: true } },
        keys: { DOCTOR: ["doctor"] } } });
    const s = plan("doctor", lex).steps[0];
    assert.equal(s.kind, "spell");
    assert.deepEqual(s.letters, [..."DOCTOR"]);
    assert.equal(s.options[0].available, false);       // offered, but disabled in the menu
});

test("missing motion file: the load fails cleanly and can be retried", async () => {
    let calls = 0;
    const lex = new Library({ manifest: {
        signs: { hello: { gloss: "HELLO", kind: "plain", keys: ["HELLO"], clip: "x" } },
        keys: { HELLO: ["hello"] } },
        fetchJSON: async () => { calls++; throw new Error("404"); } });
    await assert.rejects(lex.sign("hello"), /404/);
    await assert.rejects(lex.sign("hello"), /404/);
    assert.equal(calls, 2, "a failed load is not cached as if it succeeded");
});

test("unreliable signs never play from typed text, anywhere in the library", () => {
    const lex = new Library({ manifest, keywords, fetchJSON: noFetch });
    const unreliable = new Set(Object.entries(manifest.signs)
        .filter(([, s]) => s.status === "unreliable").map(([id]) => id));
    assert.ok(unreliable.size > 0, "the library has unreliable signs to test against");
    // every word that could reach an unreliable sign: its gloss keys and keyword keys
    const words = new Set();
    for (const [key, ids] of Object.entries(manifest.keys))
        if (ids.some(id => unreliable.has(id))) words.add(key.toLowerCase());
    for (const [key, entries] of Object.entries(keywords.keys))
        if (entries.some(e => unreliable.has(e[0]))) words.add(key.toLowerCase());
    let checked = 0;
    for (const w of words) {
        for (const s of plan(w, lex).steps) {
            assert.ok(!(s.kind === "sign" && unreliable.has(s.id)), `"${w}" played unreliable ${s.id}`);
        }
        checked++;
    }
    assert.ok(checked > 100, `checked ${checked} words`);
    // the gloss line spells them too
    const id = [...unreliable][0];
    const g = fromGlossLine(id, lex).steps[0];
    assert.equal(g.kind, "spell");
    assert.ok(g.options.some(o => o.id === id), "still offered in the menu");
});

test("playback continuity: a real 3-sign sentence has a drawable pose at every 1/60 s", () => {
    const ok = ["hello", "thank-you", "doctor"].map(id => {
        const s = manifest.signs[id];
        assert.ok(s.clip, `${id} is extracted`);
        const motion = normalizeMotion(decodeMotion(readJSON(`assets/signs/motion/${s.clip}.json`)));
        return { kind: "sign", motion, span: activeSpan(motion) };
    });
    const tl = buildTimeline(ok);
    let prev = null, worst = 0, samples = 0;
    for (let t = 0; t < tl.loopEnd; t += 1 / 60) {
        const f = sample(tl, t).frame;
        assert.ok(f && f.pose && f.pose.length === 33, `pose at t=${t.toFixed(3)}`);
        assert.ok(f.pose.every(p => Number.isFinite(p.x) && Number.isFinite(p.y)), `finite at ${t}`);
        if (prev) worst = Math.max(worst, Math.hypot(f.pose[16].x - prev[16].x, f.pose[16].y - prev[16].y));
        prev = f.pose; samples++;
    }
    // shoulder width = 1 after normalisation: no wrist teleports between refreshes
    assert.ok(worst < 0.5, `largest wrist move between refreshes ${worst.toFixed(3)} shoulder widths`);
    assert.ok(samples > 60);
});
