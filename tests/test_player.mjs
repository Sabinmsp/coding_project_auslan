// node --test tests/
// The playback controller on a fake clock: play, pause, resume, restart,
// speed, seek, next / previous sign, looping, stopping at the end, idle.
import { test } from "node:test";
import assert from "node:assert/strict";
import { Player, stepSpans } from "../frontend/src/player.js";
import { buildTimeline } from "../frontend/src/timeline.js";

const pt = (x, y) => ({ x, y });
const pose = () => Array.from({ length: 33 }, (_, i) => i === 11 ? pt(0.5, 0) : i === 12 ? pt(-0.5, 0)
    : i === 23 ? pt(0.3, 2) : i === 24 ? pt(-0.3, 2) : pt(0, 0.5));
const clip = (n, step) => ({ kind: "sign", step, motion: { fps: 30, width: 1, height: 1,
    frames: Array.from({ length: n }, () => ({ pose: pose(), left_hand: null, right_hand: null, face: null })) },
    span: [0, n - 1] });
// three signs of 1 s each, 0.22 s gaps -> duration 3.44 s
const tl = () => buildTimeline([clip(30, 0), clip(30, 1), clip(30, 2)]);
function make() {
    let ms = 0;
    const states = [];
    const p = new Player({ now: () => ms, onState: s => states.push(s) });
    const t = tl();
    p.load(t, stepSpans(t));
    return { p, adv: d => { ms += d; }, states, tl: t };
}

test("stopped at load: nothing to draw until something changes... then idle again", () => {
    const { p } = make();
    assert.ok(p.tick(), "first frame is drawn");
    assert.equal(p.tick(), null, "paused and unchanged: idle");
    assert.equal(p.t, 0);
});

test("play advances with the clock; pause freezes; resume continues from the same point", () => {
    const { p, adv } = make();
    p.play(); adv(500);
    assert.ok(Math.abs(p.tick().time - 0.5) < 1e-9);
    p.pause(); adv(5000);
    const frozen = p.tick();
    assert.ok(Math.abs(frozen.time - 0.5) < 1e-9, "wall time passing does not move a paused clock");
    assert.equal(p.tick(), null);
    p.play(); adv(250);
    assert.ok(Math.abs(p.tick().time - 0.75) < 1e-9, "resumes at 0.5, not 5.5");
});

test("speed scales the clock and changing it mid-play does not jump", () => {
    const { p, adv } = make();
    p.play(); adv(1000);
    p.tick();
    p.setSpeed(0.5);
    adv(1000);
    assert.ok(Math.abs(p.tick().time - 1.5) < 1e-9, `1.0 + 1 s at half speed = 1.5, got ${p.t}`);
    p.setSpeed(2); adv(500);
    assert.ok(Math.abs(p.tick().time - 2.5) < 1e-9);
});

test("seek pauses at the position and clamps; jumpTo keeps playing", () => {
    const { p, adv, states } = make();
    p.play(); adv(100); p.tick();
    p.seek(2.0);
    assert.equal(p.playing, false);
    assert.equal(p.tick().time, 2.0);
    p.seek(99); assert.equal(p.t, p.duration);
    p.seek(-5); assert.equal(p.t, 0);
    p.play(); adv(10); p.jumpTo(1.0); adv(500);
    assert.equal(p.playing, true);
    assert.ok(Math.abs(p.tick().time - 1.5) < 1e-9);
    assert.deepEqual(states.slice(0, 2), [true, false]);
});

test("next / previous sign; previous from inside a sign returns to its start first", () => {
    const { p, tl: t } = make();
    const [a, b, c] = stepSpans(t);
    p.seek(0.1);
    p.stepBy(1);  assert.equal(p.t, b.t0, "next -> second sign");
    p.stepBy(1);  assert.equal(p.t, c.t0);
    p.stepBy(1);  assert.equal(p.t, c.t0, "at the last sign: stays");
    p.seek(c.t0 + 0.7);
    p.stepBy(-1); assert.equal(p.t, c.t0, "inside a sign: back to its start");
    p.stepBy(-1); assert.equal(p.t, b.t0, "at a start: the previous sign");
    p.seek(0); p.stepBy(-1); assert.equal(p.t, 0);
});

test("loop wraps through the transition and says so; no-loop stops at the end", () => {
    const a = make();
    a.p.loop = true; a.p.play(); a.adv(a.tl.loopEnd * 1000 + 100);
    const f = a.p.tick();
    assert.ok(f.wrapped && a.p.playing && a.p.t < 0.2, `wrapped to ${a.p.t}`);
    const b = make();
    b.p.loop = false; b.p.play(); b.adv(10000);
    const g = b.p.tick();
    assert.equal(b.p.playing, false);
    assert.equal(g.time, b.tl.duration);
    assert.equal(b.p.tick(), null, "and then idle");
    b.p.play();
    assert.equal(b.p.t, 0, "play from the end restarts");
});

test("replay restarts from 0 and plays", () => {
    const { p, adv } = make();
    p.play(); adv(2000); p.tick();
    p.replay(); adv(100);
    assert.ok(Math.abs(p.tick().time - 0.1) < 1e-9);
});

test("a hidden tab does not make the clock jump ahead", () => {
    const { p, adv } = make();
    p.play(); adv(500); p.tick();
    adv(60000);                     // tab hidden for a minute: no frames
    p.resumeAfterHidden();
    adv(100);
    assert.ok(Math.abs(p.tick().time - 0.6) < 1e-9);
});

test("controls on an empty player do nothing and never throw", () => {
    const p = new Player({ now: () => 0 });
    p.play(); p.pause(); p.stepBy(1); p.jumpTo(3); p.seek(2); p.replay(); p.setSpeed(2);
    assert.equal(p.tick(), null);
    assert.equal(p.playing, false);
});

test("loading a new timeline replaces the old one: position resets, no stale clock", () => {
    const { p, adv } = make();
    p.play(); adv(2000); p.tick();
    const t2 = tl(); p.load(t2, stepSpans(t2));
    p.play(); adv(100);
    assert.ok(Math.abs(p.tick().time - 0.1) < 1e-9);
});

test("stress: 1,000 random control actions keep the position valid", () => {
    const { p, adv, tl: t } = make();
    let seed = 7; const rnd = () => (seed = (seed * 1103515245 + 12345) & 0x7fffffff) / 0x7fffffff;
    for (let i = 0; i < 1000; i++) {
        const r = rnd();
        if (r < 0.2) p.toggle(); else if (r < 0.3) p.seek(rnd() * 5 - 1); else if (r < 0.4) p.stepBy(rnd() < 0.5 ? -1 : 1);
        else if (r < 0.5) p.setSpeed([0.5, 0.75, 1, 1.25, 1.5][Math.floor(rnd() * 5)]);
        else if (r < 0.55) p.replay(); else if (r < 0.6) p.loop = !p.loop;
        adv(rnd() * 200);
        const f = p.tick();
        assert.ok(Number.isFinite(p.t) && p.t >= 0 && p.t <= t.loopEnd + 1e-6, `t=${p.t} at step ${i}`);
        if (f) assert.ok(f.sample && f.sample.frame && f.sample.frame.pose, `drawable at ${i}`);
    }
});
