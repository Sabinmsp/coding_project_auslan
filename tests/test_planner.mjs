// node --test tests/
// Planner logic against the REAL catalog (all 3,215 glosses), with every
// sign treated as extracted -- these tests are about choosing signs, not
// about which clips the batch has reached. Availability has its own test.
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { plan, toGlossLine, fromGlossLine, stems, numberWords } from "../frontend/src/planner.js";
import { Library } from "../frontend/src/library.js";

const catalog = JSON.parse(readFileSync(new URL("../datasets/processed/catalog.json", import.meta.url)));
function lexicon(unavailable = []) {
    const signs = {};
    for (const [id, s] of Object.entries(catalog.signs)) {
        signs[id] = { gloss: s.gloss, kind: s.kind, keys: s.keys, sense: s.sense,
                      clip: unavailable.includes(id) ? null : s.takes[0].clip };
    }
    return new Library({ manifest: { signs, keys: catalog.keys }, fetchJSON: async () => { throw new Error("no fetch in tests"); } });
}
const LEX = lexicon();
const P = text => plan(text, LEX);
const shape = p => p.steps.map(s => s.kind === "sign" ? s.id : s.kind === "spell" ? `fs:${s.letters.join("")}` : `-${s.en}`);

test("1. one known word", () => {
    assert.deepEqual(shape(P("hello")), ["hello"]);
});

test("2. multiple known words; multi-word gloss is ONE sign", () => {
    const p = P("Thank you doctor");
    assert.deepEqual(shape(p), ["thank-you", "doctor"]);
    assert.deepEqual(p.steps[0].src, [0, 1]);           // both English words map to it
});

test("3. a person's name is fingerspelled and says so", () => {
    const p = P("Hello, my name is Sabin.");
    assert.deepEqual(shape(p), ["hello", "my", "fs:NAME", "-is", "fs:SABIN"]);
    assert.match(p.steps[4].why, /name/);
    assert.match(p.steps[2].why, /no sign in the corpus/);    // NAME genuinely absent
});

test("4. unknown word -> fingerspelled, nothing invented", () => {
    const p = P("zxqv");
    assert.equal(p.steps.length, 1);
    assert.equal(p.steps[0].kind, "spell");
    assert.deepEqual(p.steps[0].letters, ["Z", "X", "Q", "V"]);
});

test("5. known + unknown + numbers + omissions", () => {
    const p = P("Pay your bill by the 10th of October 2026");
    assert.deepEqual(shape(p), ["pay", "your", "bill", "fs:BY", "-the", "ten", "-of",
                                "fs:OCTOBER", "fs:TWENTY", "fs:TWENTY", "six"]);
    assert.match(p.steps[8].why, /year 2026/);
});

test("negation uses the corpus's own negated sign", () => {
    const p = P("I don't want it");
    assert.deepEqual(shape(p).slice(0, 3), ["i", "-don't", "want-not-want"]);
    assert.equal(p.steps[2].match, "exact");
});

test("WANT / GOOD / KNOW never resolve to their NEGATED signs", () => {
    for (const w of ["want", "good", "know"]) {
        const s = P(`I ${w}`).steps[1];
        assert.equal(s.kind, "spell", `${w} must be spelled, got ${s.id}`);
    }
    assert.deepEqual(shape(P("no good")), ["good-no-good"]);
});

test("specific sense needs evidence in the sentence", () => {
    // CAN only exists as CAN (TIN): the modal must not become a tin can
    const modal = P("I can help").steps[1];
    assert.equal(modal.kind, "spell");
    assert.ok(modal.options.some(o => o.id === "can-tin"), "sense offered as an option");
    const tin = P("open the tin can").steps.find(s => s.key === "CAN");
    assert.equal(tin.id, "can-tin");
    assert.equal(tin.uncertain, true);
    assert.equal(P("water").steps[0].kind, "spell");
    assert.equal(P("water the garden with a hose").steps[0].id, "water-hose");
});

test("10. multiple variants: plain preferred, context picks a sense, both reviewable", () => {
    const plain = P("open").steps[0];
    assert.equal(plain.id, "open");
    assert.equal(plain.uncertain, false);
    assert.ok(plain.options.length >= 6);
    const door = P("open the door").steps[0];
    assert.equal(door.id, "open-door");
    assert.equal(door.uncertain, true);                   // flagged for review
    assert.equal(door.match, "context");
});

test("stems only when the word itself has no sign", () => {
    const p = P("paid bills");
    assert.deepEqual(shape(p), ["pay", "bill"]);
    assert.equal(p.steps[0].match, "stem");
    assert.ok(stems("running").includes("run"));
    assert.ok(stems("studies").includes("study"));
});

test("time adverb first; dates stay put", () => {
    const p = P("I go home tomorrow");
    assert.equal(p.steps[0].id, "tomorrow");
    assert.equal(p.steps[0].moved, "time first");
    assert.deepEqual(shape(plan("I go home tomorrow", LEX, { auslanOrder: false })).at(-1), "tomorrow");
});

test("wh-question: wh-sign last, and the missing facial grammar is stated", () => {
    const p = P("Who is your doctor?");
    assert.equal(p.question, "wh");
    assert.equal(p.steps.at(-1).id, "who");
    assert.match(p.notes[0], /NOT expressed/);
    assert.equal(P("Are you deaf?").question, "yn");
});

test("8. repeated signs stay repeated", () => {
    assert.deepEqual(shape(P("hello hello")), ["hello", "hello"]);
});

test("7. long sentence: complete and fast", () => {
    const text = Array(12).fill("Please pay the water bill before tomorrow and help your mother").join(". ");
    const t0 = performance.now();
    const p = P(text);
    const ms = performance.now() - t0;
    assert.ok(p.steps.length > 100);
    assert.ok(ms < 200, `planned in ${ms.toFixed(0)}ms`);
    assert.ok(p.steps.every(s => ["sign", "spell", "omit"].includes(s.kind)));
});

test("a sign not yet extracted is fingerspelled, and says the sign exists", () => {
    const s = plan("doctor", lexicon(["doctor"])).steps[0];
    assert.equal(s.kind, "spell");
    assert.equal(s.pending, "doctor");
    assert.match(s.why, /not extracted yet/);
});

test("pending multi-word sign falls back word by word, never run-together", () => {
    const p = plan("I don't want it", lexicon(["want-not-want"]));
    assert.deepEqual(shape(p).slice(0, 4), ["i", "-don't", "not", "fs:WANT"]);
    assert.equal(p.steps[2].pending, "want-not-want");
    assert.match(p.steps[2].why, /NOT WANT\) would fit better/);
});

test("an UNRELIABLE sign is fingerspelled by default, kept as a menu option", () => {
    const signs = {};
    for (const [id, s] of Object.entries(catalog.signs)) {
        signs[id] = { gloss: s.gloss, kind: s.kind, keys: s.keys, sense: s.sense, clip: s.takes[0].clip };
    }
    signs["help"].status = "unreliable"; signs["help"].flags = ["hand coverage 17%"];
    signs["pay"].status = "review"; signs["pay"].flags = ["tracking gap > 0.2 s"];
    const lex = new Library({ manifest: { signs, keys: catalog.keys }, fetchJSON: async () => { throw new Error(); } });
    const p = plan("help me pay", lex);
    const help = p.steps[0], pay = p.steps.find(s => s.key === "PAY");
    assert.equal(help.kind, "spell");
    assert.match(help.why, /unreliable tracking/);
    assert.ok(help.options.some(o => o.id === "help" && o.status === "unreliable"));
    assert.equal(pay.kind, "sign");                       // review: plays, flagged
    assert.equal(pay.low, true);
    assert.deepEqual(pay.flags, ["tracking gap > 0.2 s"]);
});

// ---- dictionary keywords (assets/signs/keywords.json) ----
const keywords = JSON.parse(readFileSync(new URL("../assets/signs/keywords.json", import.meta.url)));
function keywordLexicon() {
    const signs = {};
    for (const [id, s] of Object.entries(catalog.signs)) {
        signs[id] = { gloss: s.gloss, kind: s.kind, keys: s.keys, sense: s.sense, clip: s.takes[0].clip };
    }
    return new Library({ manifest: { signs, keys: catalog.keys }, keywords,
                         fetchJSON: async () => { throw new Error("no fetch in tests"); } });
}
const KW = keywordLexicon();
const K = text => plan(text, KW);

test("keywords: a word that is no gloss finds its sign through the dictionary", () => {
    const can = K("I can help").steps[1];
    assert.equal(can.id, "able");                    // not CAN (TIN), not fingerspelled
    assert.equal(can.match, "keyword");
    assert.equal(can.uncertain, false);
    assert.match(can.why, /not CAN \(TIN\)/);
    assert.equal(K("I forgot").steps[1].id, "forget");
    assert.equal(K("Dr Smith").steps[0].id, "doctor");
    assert.equal(K("Dr Smith").steps[1].kind, "spell");
});

test("keywords: several signs list the word -> best chosen, marked for review", () => {
    const r = K("I remember you").steps[1];
    assert.equal(r.id, "recollect");                 // listed 2nd by RECOLLECT, 7th by PRIZE
    assert.equal(r.uncertain, true);
    assert.ok(r.options.some(o => o.id === "prize"));
    assert.equal(K("remembered").steps[0].id, "recollect");   // through the stem
});

test("keywords: a loosely listed sign is spelled and offered; a strong one plays", () => {
    const name = K("name").steps[0];                     // NICKNAME lists "name" 4th of 6
    assert.equal(name.kind, "spell");
    assert.match(name.why, /only loosely/);
    assert.ok(name.options.some(o => o.id === "nickname"));
    assert.equal(K("come").steps[0].id, "coming");      // a form of the sign's own name
    assert.equal(K("today").steps[0].id, "now");        // listed 2nd by NOW
});

test("keywords never reach a negated sign through its bare word", () => {
    assert.equal(K("I want it").steps[1].kind, "spell");      // no WANT (NOT WANT)
    for (const [text, banned] of [["I know", "know-not-know"], ["good", "good-no-good"],
                                  ["I like it", "like-not-like"], ["I have", "be-not-be"]]) {
        assert.ok(K(text).steps.every(s => s.id !== banned), `${text} -> ${banned}`);
    }
});

test("keywords never override a gloss name or its stem", () => {
    assert.deepEqual(K("hello pay").steps.map(s => s.id), ["hello", "pay"]);
    const learned = K("I learned it").steps[1];
    assert.equal(learned.id, "learn");                       // not ENLIGHTENMENT ("learned (knowledgeable)")
    assert.equal(learned.match, "stem");
});

test("a sense needs evidence from OTHER words (regression: 'time')", () => {
    assert.equal(K("pay on time").steps.find(s => s.key === "TIME").id, "time");
    assert.equal(P("time").steps[0].id, "time");             // not TIME (BETWEEN TWO CLOCK TIMES)
});

test("gloss line: round trip, and every token validated", () => {
    const p = P("Hello, my name is Sabin.");
    const line = toGlossLine(p);
    assert.equal(line, "hello my fs:NAME fs:SABIN");
    assert.deepEqual(shape(fromGlossLine(line, LEX)), ["hello", "my", "fs:NAME", "fs:SABIN"]);
    const bad = fromGlossLine("hello not-a-sign water", LEX);
    assert.deepEqual(shape(bad), ["hello", "fs:NOTASIGN", "fs:WATER"]);
    assert.equal(bad.notes.length, 2);                    // both problems reported
});

test("number words", () => {
    assert.deepEqual(numberWords(26), ["twenty", "six"]);
    assert.deepEqual(numberWords(105), ["one", "hundred", "five"]);
});
