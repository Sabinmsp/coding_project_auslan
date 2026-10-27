// node --test tests/
// Code Fair hardening (2026-10-27): spike removal, held hands instead of
// blinking, compact fingerspelling, timeline boundaries, and the planner on
// the demo sentences, empty input, punctuation, repeats and spell reasons.
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { plan, fromGlossLine } from "../frontend/src/planner.js";
import { Library, decodeMotion, normalizeMotion, activeSpan, despike, letterCore, CORE } from "../frontend/src/library.js";
import { buildTimeline, sample, FADE } from "../frontend/src/timeline.js";

const root = new URL("../", import.meta.url);
const readJSON = rel => JSON.parse(readFileSync(new URL(rel, root)));
const manifest = readJSON("assets/signs/manifest.json");
const keywords = readJSON("assets/signs/keywords.json");
const letters = readJSON("assets/fingerspelling/letters.json");
const lex = new Library({ manifest, keywords, fetchJSON: async () => { throw new Error("no fetch"); } });
const realSign = id => {
    const m = normalizeMotion(despike(decodeMotion(readJSON(`assets/signs/motion/${manifest.signs[id].clip}.json`))));
    return { kind: "sign", id, motion: m, span: activeSpan(m) };
};

// ---- synthetic clips: 21-point hands, 33-point poses ----------------------
const pt = (x, y) => ({ x, y });
const hand = (x, y) => Array.from({ length: 21 }, (_, i) => pt(x + i * 0.01, y - i * 0.01));
const pose = (wx, wy) => Array.from({ length: 33 }, (_, i) =>
    i === 15 ? pt(wx, wy) : i === 16 ? pt(-wx, wy) : i === 11 ? pt(0.5, 0) : i === 12 ? pt(-0.5, 0)
    : i === 23 ? pt(0.3, 2) : i === 24 ? pt(-0.3, 2) : pt(0, -0.5));
function clip(n, handAt = () => true) {
    const frames = Array.from({ length: n }, (_, i) => {
        const wx = 0.4 + i * 0.01, wy = 0.5;
        return { pose: pose(wx, wy), left_hand: handAt(i) ? hand(wx, wy) : null, right_hand: null, face: null };
    });
    return { kind: "sign", motion: { fps: 30, width: 1, height: 1, frames }, span: [0, n - 1] };
}

// ---------------------------------------------------------------------------
test("despike: removes a one-frame spike, keeps steady motion exactly", () => {
    const frames = Array.from({ length: 9 }, (_, i) => ({ pose: null, right_hand: null, face: null,
        left_hand: [pt(i * 0.1, 0)] }));
    frames[4].left_hand = [pt(5, 3)];                      // a single-frame glitch
    const out = despike({ frames }).frames;
    assert.deepEqual(out[4].left_hand[0], pt(0.5, 0), "spike replaced by a measured neighbour value");
    for (const i of [1, 2, 6, 7]) assert.deepEqual(out[i].left_hand[0], frames[i].left_hand[0], `frame ${i} untouched`);
    assert.deepEqual(out[0].left_hand, frames[0].left_hand, "first frame untouched");
});

test("despike: absent tracks stay absent and are not bridged", () => {
    const frames = [0, 1, 2, 3].map(i => ({ pose: null, right_hand: null, face: null,
        left_hand: i === 2 ? null : [pt(i, i)] }));
    const out = despike({ frames }).frames;
    assert.equal(out[2].left_hand, null);
    assert.deepEqual(out[1].left_hand, frames[1].left_hand, "a neighbour of a gap is left alone");
});

test("despike on real clips: same frame count, every value one of its 3 neighbours", () => {
    for (const id of ["pay", "help", "hello"]) {
        const raw = normalizeMotion(decodeMotion(readJSON(`assets/signs/motion/${manifest.signs[id].clip}.json`)));
        const sm = despike(raw);
        assert.equal(sm.frames.length, raw.frames.length);
        raw.frames.forEach((f, i) => {
            if (!f.right_hand || !sm.frames[i].right_hand) return;
            const near = [i - 1, i, i + 1].map(j => raw.frames[j]?.right_hand).filter(Boolean);
            sm.frames[i].right_hand.forEach((p, k) => {
                assert.ok(near.some(h => h[k].x === p.x), `${id} frame ${i} x is measured`);
                assert.ok(near.some(h => h[k].y === p.y), `${id} frame ${i} y is measured`);
            });
        });
    }
});

test("held hand: a short dropout fades instead of blinking, shape unchanged", () => {
    const c = clip(20, i => !(i >= 8 && i <= 9));          // 2 frames lost
    const tl = buildTimeline([c]);
    const s = sample(tl, 8.5 / 30);
    const h = s.frame.left_hand;
    assert.ok(h, "the hand is still drawn during the dropout");
    assert.ok(s.frame.held.left_hand > 0 && s.frame.held.left_hand < 1, "and marked as held, faded");
    // rigid: every finger offset from the hand root is the measured one
    const src = c.motion.frames[7].left_hand;
    h.forEach((p, k) => {
        assert.ok(Math.abs((p.x - h[0].x) - (src[k].x - src[0].x)) < 1e-9);
        assert.ok(Math.abs((p.y - h[0].y) - (src[k].y - src[0].y)) < 1e-9);
    });
    // and it follows the arm's measured wrist
    const w = s.frame.pose[15];
    assert.ok(Math.abs((h[0].x - src[0].x) - (w.x - c.motion.frames[7].pose[15].x)) < 1e-9);
    // a measured frame is never marked held
    assert.equal(sample(tl, 3 / 30).frame.held, undefined);
});

test("held hand: never longer than FADE frames, and fading out with distance", () => {
    const c = clip(40, i => i < 10);                        // hand gone for good after frame 9
    const tl = buildTimeline([c]);
    const a = sample(tl, 11 / 30).frame, b = sample(tl, 14 / 30).frame;
    assert.ok(a.held.left_hand > b.held.left_hand, "fades with distance from the measurement");
    assert.equal(sample(tl, (9 + FADE + 1.5) / 30).frame.left_hand, null, "gone beyond FADE");
    assert.equal(sample(tl, 11 / 30, { fade: 0 }).frame.left_hand, null, "fade: 0 = raw behaviour");
});

test("transition: a hand on one side fades out across the gap", () => {
    const A = clip(10), B = clip(10, () => false);
    const tl = buildTimeline([A, B]);
    const gap = tl.items.find(i => i.type === "gap" && !i.wrap);
    const early = sample(tl, gap.t0 + 0.02).frame, late = sample(tl, gap.t1 - 0.02).frame;
    assert.ok(early.left_hand && late.left_hand);
    assert.ok(early.held.left_hand > 0.9 && late.held.left_hand < 0.1, "1 -> 0 across the gap");
});

test("timeline boundaries: before 0, at the end, past loopEnd, empty", () => {
    const tl = buildTimeline([realSign("hello"), realSign("you")]);
    for (const t of [-5, 0, tl.duration, tl.duration + 0.05, tl.loopEnd, tl.loopEnd + 10]) {
        const s = sample(tl, t);
        assert.ok(s && s.frame && s.frame.pose && s.frame.pose.length === 33, `drawable at t=${t}`);
    }
    assert.equal(sample(buildTimeline([]), 0), null);
});

test("long sentence on real clips: every 1/60 s drawable, no hand blinks shorter than a fade", () => {
    const ids = ["thank-you", "doctor", "pay", "bill", "tomorrow", "help", "learn", "auslan", "again", "bad"];
    const tl = buildTimeline(ids.map(realSign));
    let prev = null, popped = 0;
    for (let t = 0; t < tl.duration; t += 1 / 60) {
        const f = sample(tl, t).frame;
        assert.ok(f.pose, `pose at ${t.toFixed(3)}`);
        for (const k of ["left_hand", "right_hand"]) {
            // vanishing from FULL opacity in one refresh is the flicker this fixes
            if (prev && prev[k] && !(prev.held && prev.held[k] !== undefined) && !f[k]) popped++;
        }
        prev = f;
    }
    assert.ok(popped <= 2, `${popped} hands vanished from full opacity`);
});

test("letter cores: a contiguous sub-span of measured frames, at most CORE.MAX s", () => {
    for (const ch of Object.keys(letters)) {
        const m = normalizeMotion(decodeMotion(readJSON(letters[ch].motion)));
        const span = activeSpan(m), core = letterCore(m, span);
        assert.ok(core[0] >= span[0] && core[1] <= span[1] && core[0] <= core[1], `${ch} inside its span`);
        assert.ok((core[1] - core[0] + 1) / m.fps <= CORE.MAX + 1e-9, `${ch} at most ${CORE.MAX}s`);
    }
    // nothing still enough: the span is returned unchanged
    const moving = clip(20).motion;
    moving.frames.forEach((f, i) => { f.pose[15] = pt(i * 0.2, 0); });
    assert.deepEqual(letterCore(moving, [0, 19]), [0, 19]);
});

// ---- planner -----------------------------------------------------------------
const shape = p => p.steps.map(s => s.kind === "sign" ? s.id : s.kind === "spell" ? `fs:${s.letters.join("")}` : `-${s.en}`).join(" ");

test("demo sentences: every word accounted for, nothing unreliable plays", () => {
    const demos = ["Hello, how are you?", "My name is Sabin.", "I need help.", "Where is the hospital?",
                   "I want to learn Auslan.", "Thank you for helping me.", "Please pay your bill tomorrow."];
    for (const text of demos) {
        const p = plan(text, lex);
        assert.ok(p.steps.length > 0, text);
        for (const s of p.steps) {
            assert.ok(["sign", "spell", "omit"].includes(s.kind), `${text}: ${s.kind}`);
            assert.ok(s.why, `${text}: every step explains itself`);
            if (s.kind === "sign") assert.notEqual(manifest.signs[s.id].status, "unreliable", `${text}: ${s.id}`);
            if (s.kind === "spell") assert.ok(s.reason, `${text}: spelled "${s.en}" says why`);
        }
    }
    assert.equal(shape(plan("Please pay your bill tomorrow.", lex)), "tomorrow fs:PLEASE pay your bill");
});

test("spell reasons: name vs no sign vs requested", () => {
    const p = plan("My name is Sabin.", lex);
    assert.equal(p.steps.find(s => s.en.toLowerCase() === "sabin").reason, "name");
    assert.equal(plan("zxqv", lex).steps[0].reason, "nosign");
    assert.equal(fromGlossLine("hello fs:SABIN", lex).steps[1].reason, "requested");
});

test("empty, blank and punctuation-only input plan nothing and do not throw", () => {
    for (const t of ["", "   ", "...", "?!", "\n\t"]) assert.equal(plan(t, lex).steps.length, 0, JSON.stringify(t));
    assert.equal(shape(plan("Hello!!! ... ???", lex)), "hello");
});

test("repeated words stay repeated; punctuation never becomes a sign", () => {
    assert.equal(shape(plan("hello hello hello", lex)), "hello hello hello");
    assert.equal(shape(plan("hello, hello.", lex)), "hello hello");
});

test("rapid input changes: planning is pure (same text -> same plan)", () => {
    const texts = ["I need help.", "Where is the hospital?", "I need help."];
    const out = texts.map(t => shape(plan(t, lex)));
    assert.equal(out[0], out[2]);
});

test("partial web build: the collector keeps every sign a listed sentence plays, and its options", async () => {
    const { execFileSync } = await import("node:child_process");
    const { writeFileSync, mkdtempSync } = await import("node:fs");
    const { tmpdir } = await import("node:os");
    const dir = mkdtempSync(`${tmpdir()}/collect-`);
    writeFileSync(`${dir}/t.txt`, "# comment\nPlease pay your bill tomorrow.\n");
    const ids = JSON.parse(execFileSync(process.execPath, [(await import("node:url")).fileURLToPath(new URL("../scripts/collect_sign_ids.mjs", import.meta.url)), `${dir}/t.txt`]));
    for (const s of plan("Please pay your bill tomorrow.", lex).steps) {
        if (s.kind === "sign") assert.ok(ids.includes(s.id), s.id);
        for (const o of s.options || []) assert.ok(ids.includes(o.id), `option ${o.id}`);
    }
    assert.ok(ids.includes("hello"), "quick picks always included");
    assert.ok(ids.length < 200, `${ids.length} signs: a subset, not the library`);
});
