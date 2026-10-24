// Library decoding, normalisation, trimming, caching and the timeline,
// against real extracted clips from assets/signs/motion/.
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { decodeMotion, normalizeMotion, activeSpan, wristHeights, LRU, Library } from "../frontend/src/library.js";
import { buildTimeline, sample, lerpFrame, mixFrames, allFrames, GAP } from "../frontend/src/timeline.js";

const root = new URL("../", import.meta.url);
const readJSON = rel => JSON.parse(readFileSync(new URL(rel, root)));
const FINISH = "assets/signs/motion/20062.json";      // two-handed
const HELLO = "assets/signs/motion/01970.json";       // one-handed

test("decode v2: frame count, absent tracks stay absent", () => {
    const raw = readJSON(FINISH);
    const m = decodeMotion(raw);
    assert.equal(m.frames.length, raw.n);
    raw.right_hand.forEach((h, i) => {
        assert.equal(m.frames[i].right_hand === null, h === 0);
        assert.equal(raw.src.right_hand[i] === "-", h === 0);   // provenance agrees
    });
    assert.equal(m.frames[0].face.length, raw.face_indices.length);
    const p = m.frames[20].pose[11];
    assert.equal(p.x, raw.pose[20][22] / raw.scale);
});

test("missing landmark frames are kept as gaps, never filled", () => {
    const m = decodeMotion(readJSON(FINISH));
    const gaps = m.frames.filter(f => !f.right_hand).length;
    assert.ok(gaps > 0, "this clip has untracked right-hand frames");
    // and the player sees exactly those gaps after normalisation
    const n = normalizeMotion(m);
    assert.equal(n.frames.filter(f => !f.right_hand).length, gaps);
});

test("normalisation is one similarity transform per clip", () => {
    const m = decodeMotion(readJSON(FINISH));
    const n = normalizeMotion(m);
    const a = m.width / m.height;
    const d = (P, i, j, asp) => Math.hypot((P[i].x - P[j].x) * asp, P[i].y - P[j].y);
    // every distance scales by the same factor -> all ratios preserved
    const f0 = m.frames[30], g0 = n.frames[30];
    const k1 = d(g0.pose, 15, 16, 1) / d(f0.pose, 15, 16, a);
    const k2 = d(g0.pose, 0, 24, 1) / d(f0.pose, 0, 24, a);
    const k3 = d(g0.right_hand ?? g0.left_hand, 0, 12, 1) / d(f0.right_hand ?? f0.left_hand, 0, 12, a);
    assert.ok(Math.abs(k1 - k2) < 1e-9 && Math.abs(k1 - k3) < 1e-9);
    // median shoulder line maps to origin, width 1
    const mids = n.frames.filter(f => f.pose).map(f => (f.pose[11].x + f.pose[12].x) / 2).sort((x, y) => x - y);
    assert.ok(Math.abs(mids[mids.length >> 1]) < 0.02);
});

test("two different signers land on the same body frame", () => {
    const shoulders = rel => {
        const n = normalizeMotion(decodeMotion(readJSON(rel)));
        const f = n.frames[5].pose;
        return Math.hypot(f[11].x - f[12].x, f[11].y - f[12].y);
    };
    assert.ok(Math.abs(shoulders(FINISH) - 1) < 0.08);
    assert.ok(Math.abs(shoulders(HELLO) - 1) < 0.08);
});

test("rest trimming cuts only leading/trailing rest", () => {
    const m = normalizeMotion(decodeMotion(readJSON(FINISH)));
    const [s, e] = activeSpan(m);
    const rel = wristHeights(m);
    assert.ok(s > 0 && e < m.frames.length - 1, `trimmed to ${s}..${e} of ${m.frames.length}`);
    // nothing raised is cut: every frame outside the span is near rest
    for (let i = 0; i < m.frames.length; i++) {
        if (i < s || i > e) assert.ok(rel[i] > 0.75, `frame ${i} rel ${rel[i].toFixed(2)} cut while raised`);
    }
});

test("a clip with no rest is never trimmed", () => {
    const m = normalizeMotion(decodeMotion(readJSON(FINISH)));
    const [s, e] = activeSpan(m);
    const cut = { ...m, frames: m.frames.slice(s + 3, e - 3) };   // starts and ends mid-sign
    assert.deepEqual(activeSpan(cut), [0, cut.frames.length - 1]);
});

test("LRU evicts least recently used", () => {
    const c = new LRU(2);
    c.set("a", 1); c.set("b", 2); c.get("a"); c.set("c", 3);
    assert.equal(c.get("b"), undefined);
    assert.equal(c.get("a"), 1);
});

test("Library: lazy, cached, one fetch per sign however often it is used", async () => {
    let fetches = 0;
    const manifest = { signs: { finish: { gloss: "FINISH", kind: "plain", keys: ["FINISH"], clip: "20062" },
                                later: { gloss: "LATER", kind: "plain", keys: ["LATER"], clip: null } },
                       keys: { FINISH: ["finish"], LATER: ["later"] } };
    const lib = new Library({ manifest, base: ".", fetchJSON: async url => {
        fetches++; return readJSON(url.replace(/^\.\//, "")); } });
    assert.equal(fetches, 0, "nothing loaded up front");
    const [a, b] = await Promise.all([lib.sign("finish"), lib.sign("finish")]);
    assert.equal(fetches, 1);
    assert.equal(a, b);
    assert.equal(a.video, "./assets/signs/videos/20062.mp4");
    await assert.rejects(lib.sign("later"), /not available/);
});

test("timeline: clips keep their own timing; gaps don't invent hands", async () => {
    const clip = (rel, kind) => {
        const motion = normalizeMotion(decodeMotion(readJSON(rel)));
        return { kind, motion, span: activeSpan(motion) };
    };
    const A = clip(HELLO, "sign"), B = clip(FINISH, "sign");
    const tl = buildTimeline([A, B]);
    const durA = (A.span[1] - A.span[0] + 1) / A.motion.fps;
    const durB = (B.span[1] - B.span[0] + 1) / B.motion.fps;
    assert.ok(Math.abs(tl.duration - (durA + durB + 0.22)) < 1e-9);

    // at a recorded frame's own instant, the recorded frame itself
    const s0 = sample(tl, 0);
    assert.equal(s0.frame, A.motion.frames[A.span[0]]);
    const t = tl.items[2].t0 + 10 / B.motion.fps;
    assert.equal(sample(tl, t).local, B.span[0] + 10);
    assert.equal(sample(tl, t).frame, B.motion.frames[B.span[0] + 10]);
    // halfway to the next recorded frame: exactly halfway between the two
    const f0 = B.motion.frames[B.span[0] + 10], f1 = B.motion.frames[B.span[0] + 11];
    const mid = sample(tl, t + 0.5 / B.motion.fps).frame;
    for (const j of [11, 15, 16]) {
        assert.ok(Math.abs(mid.pose[j].x - (f0.pose[j].x + f1.pose[j].x) / 2) < 1e-9);
        assert.ok(Math.abs(mid.pose[j].y - (f0.pose[j].y + f1.pose[j].y) / 2) < 1e-9);
    }

    // gap: halfway between, and a hand missing on one side is not drawn
    const g = tl.items[1];
    const inGap = sample(tl, (g.t0 + g.t1) / 2);
    assert.equal(inGap.local, null);
    assert.ok(inGap.frame.pose);
    const fake = lerpFrame({ pose: null, left_hand: null, right_hand: [{ x: 0, y: 0 }] },
                           { pose: null, left_hand: [{ x: 1, y: 1 }], right_hand: [{ x: 1, y: 1 }] }, 0.5);
    assert.equal(fake.left_hand, null);
    assert.deepEqual(fake.right_hand, [{ x: 0.5, y: 0.5 }]);

    assert.equal([...allFrames(tl)].length, (A.span[1] - A.span[0] + 1) + (B.span[1] - B.span[0] + 1));
});

test("between two recorded frames: a hand present in only one comes from the nearer frame", () => {
    const pose = [{ x: 0, y: 0 }], hand = [{ x: 1, y: 1 }];
    const A = { pose, left_hand: hand, right_hand: null, face: null };
    const B = { pose: [{ x: 2, y: 2 }], left_hand: null, right_hand: hand, face: null };
    const early = mixFrames(A, B, 0.25), late = mixFrames(A, B, 0.75);
    assert.deepEqual(early.pose, [{ x: 0.5, y: 0.5 }]);
    assert.equal(early.left_hand, hand);        // A's hand, not a blend with nothing
    assert.equal(early.right_hand, null);
    assert.equal(late.left_hand, null);
    assert.equal(late.right_hand, hand);
});

test("looping wraps through a transition instead of jumping back", () => {
    const motion = normalizeMotion(decodeMotion(readJSON(HELLO)));
    const tl = buildTimeline([{ kind: "sign", motion, span: activeSpan(motion) }]);
    assert.ok(Math.abs(tl.loopEnd - (tl.duration + GAP.word)) < 1e-9);
    const wrap = tl.items.at(-1);
    assert.equal(wrap.wrap, true);
    // halfway through the wrap: between the last and the first pose
    const last = motion.frames[tl.clips[0].span[1]].pose[16], first = motion.frames[tl.clips[0].span[0]].pose[16];
    const mid = sample(tl, (wrap.t0 + wrap.t1) / 2).frame.pose[16];
    const lo = Math.min(last.y, first.y) - 1e-9, hi = Math.max(last.y, first.y) + 1e-9;
    assert.ok(mid.y >= lo && mid.y <= hi);
    // past the end of the wrap, sampling clamps
    assert.ok(sample(tl, tl.loopEnd + 5).frame);
});
