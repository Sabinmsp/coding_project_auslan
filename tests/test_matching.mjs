// node --test tests/
// English -> sign matching on everyday sentences (scripts/matching_report.mjs),
// the NAME investigation, and the matching rules added on 2026-10-27.
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { plan } from "../frontend/src/planner.js";
import { Library } from "../frontend/src/library.js";
import { analyse, totals, SENTENCES } from "../scripts/matching_report.mjs";

const root = new URL("../", import.meta.url);
const readJSON = rel => JSON.parse(readFileSync(new URL(rel, root)));
const manifest = readJSON("assets/signs/manifest.json");
const lex = new Library({ manifest, keywords: readJSON("assets/signs/keywords.json") });
const step = (text, en) => plan(text, lex).steps.find(s => (s.en || "").toLowerCase() === en);

test("30 representative sentences: coverage does not regress (83.9% measured 2026-10-27)", () => {
    assert.equal(SENTENCES.length, 30);
    const t = totals(analyse(lex));
    assert.ok(t.coverage >= 0.839, `coverage ${(100 * t.coverage).toFixed(1)}%`);
    assert.ok(t.confident >= 0.741, `confident ${(100 * t.confident).toFixed(1)}%`);
});

test("NAME: no plain NAME sign in the corpus; NICKNAME is offered, not played", () => {
    assert.equal(manifest.keys.NAME, undefined, "no gloss NAME");
    const s = step("My name is Sabin.", "name");
    assert.equal(s.kind, "spell");
    assert.equal(s.reason, "loose");
    assert.ok(s.options.some(o => o.id === "nickname"), "NICKNAME in the menu");
    assert.equal(step("My name is Sabin.", "sabin").reason, "name");
});

test("plurals and past tense reach the base sign", () => {
    assert.equal(step("Students must attend classes.", "students").gloss, "STUDENT");
    assert.equal(step("She helped me", "helped").gloss, "HELP");
});

test("related forms play, marked for review; ambiguous English words do not", () => {
    const h = step("I am happy", "happy");
    assert.equal(h.gloss, "HAPPINESS"); assert.ok(h.uncertain);
    const w = step("Where is the toilet?", "where");
    assert.equal(w.gloss, "WHEREABOUTS"); assert.ok(w.uncertain);
    for (const [text, en, bad] of [["What do you mean?", "mean", "MEANNESS"], ["It is hard", "hard", "HARDNESS"]]) {
        const s = step(text, en);
        assert.ok(!(s && s.kind === "sign" && s.gloss === bad), `${en} must not become ${bad}`);
    }
});

test("clipped words use the full word's sign", () => {
    assert.equal(step("I have an exam", "exam").gloss, "EXAMINED");
    assert.equal(step("We watch tv", "tv").gloss, "TELEVISION");
});

test("DEAF MUTE is shown as DEAF; the corpus label is kept", () => {
    const s = step("My friend is deaf.", "deaf");
    assert.equal(s.id, "deaf-mute");
    assert.equal(s.gloss, "DEAF");
    assert.equal(lex.byId("deaf-mute").corpusGloss, "DEAF MUTE");
});

test("no usable sign is disabled: typing a plain sign's own name plays a sign", () => {
    let checked = 0;
    for (const [id, s] of Object.entries(manifest.signs)) {
        if (s.kind !== "plain" || !s.clip || s.status === "unreliable") continue;
        if (["A", "ARE", "TO"].includes(s.keys[0])) continue;     // grammar words the planner omits by design
        const steps = plan(s.keys[0].toLowerCase(), lex).steps.filter(x => x.kind !== "omit");
        assert.ok(steps.length && steps.every(x => x.kind === "sign"), `${s.keys[0]} -> ${steps.map(x => x.kind + ":" + (x.gloss || x.letters?.join(""))).join(" ")}`);
        checked++;
    }
    assert.ok(checked > 2000, `${checked} signs checked`);
});
