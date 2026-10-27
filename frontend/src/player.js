// ======================================================
// Playback controller: the ONE clock.
//
// No DOM, no drawing, no network: it holds a timeline, a position and a
// play state, and answers "what should be on screen now?". The page calls
// tick() once per animation frame and draws what it returns; captions, the
// scrubber, the step tiles and the reference video all follow `time`, so
// nothing can drift out of step.
//
//   position   t = elapsed wall-clock seconds x speed, measured from a
//              start mark that is re-set whenever playing starts, the speed
//              changes, the playhead jumps, or the tab comes back
//   idle       paused and nothing changed: tick() returns null, so a paused
//              page does no work at all
//   looping    plays the wrap transition (last pose -> first) up to loopEnd
//   steps      [{n, t0, t1}] one per plan step, for next / previous sign
//
// `now` is injectable (tests drive a fake clock).
// ======================================================
import { sample } from "./timeline.js";

export class Player {
    constructor({ now = () => performance.now(), onState = () => {} } = {}) {
        this.now = now;
        this.onState = onState;          // called when playing / paused flips
        this.speed = 1;
        this.loop = true;
        this.clear();
    }

    clear() {
        this.tl = null;
        this.steps = [];
        this.t = 0;
        this.playing = false;
        this.dirty = true;               // something changed: draw again
        this._start = 0;
        this.wrapped = false;            // set when a loop restarts (page re-syncs its video)
    }

    // A new timeline replaces the old one; the position restarts at 0.
    load(tl, steps = []) {
        this.tl = tl;
        this.steps = steps;
        this.t = 0;
        this.dirty = true;
        this.wrapped = false;
        this._mark();
    }

    get duration() { return this.tl ? this.tl.duration : 0; }

    _mark() { this._start = this.now() - this.t / this.speed * 1000; }
    markDirty() { this.dirty = true; }

    play() {
        if (!this.tl) return;
        if (this.t >= this.tl.duration - 1e-3) this.t = 0;
        this._mark();
        this.playing = true;
        this.dirty = true;
        this.onState(true);
    }

    pause() {
        this.playing = false;
        this.dirty = true;
        this.onState(false);
    }

    toggle() { if (this.playing) this.pause(); else this.play(); }

    replay() { this.t = 0; this.play(); }

    setSpeed(s) {
        this.speed = s;
        if (this.playing) this._mark();
    }

    // Move the playhead and pause (the scrubber, programmatic seeks).
    seek(t) {
        this.pause();
        this.t = this.tl ? Math.max(0, Math.min(t, this.tl.duration)) : 0;
        this.dirty = true;
    }

    // Move the playhead, keeping play / pause as it is (step buttons, tiles).
    jumpTo(t) {
        if (!this.tl) return;
        this.t = Math.max(0, Math.min(t, this.tl.duration - 1e-3));
        if (this.playing) this._mark();
        this.dirty = true;
        this.wrapped = true;             // the video must find its place again
    }

    // d = +1 next sign, -1 previous. From well inside a sign, "previous"
    // first returns to that sign's start.
    stepBy(d) {
        if (!this.tl || !this.steps.length) return;
        let i = this.steps.findIndex(s => this.t < s.t1);
        if (i === -1) i = this.steps.length - 1;
        if (d < 0 && this.t - this.steps[i].t0 > 0.4) d = 0;
        const j = Math.max(0, Math.min(this.steps.length - 1, i + d));
        this.jumpTo(this.steps[j].t0);
    }

    // The tab was hidden: no frames were drawn, the wall clock moved on.
    resumeAfterHidden() { if (this.playing) this._mark(); }

    // Once per animation frame. Returns null when there is nothing to draw,
    // else { sample, time, wrapped } where `time` is the position clamped to
    // the sentence (the loop's wrap transition lies beyond it).
    tick() {
        const tl = this.tl;
        if (!tl) return null;
        let wrapped = this.wrapped;      // a jump since the last frame
        this.wrapped = false;
        if (this.playing) {
            this.t = (this.now() - this._start) / 1000 * this.speed;
            const end = this.loop ? tl.loopEnd : tl.duration;
            if (this.t >= end) {
                if (this.loop) {
                    this.t %= end;
                    this._mark();
                    wrapped = true;
                } else {
                    this.t = tl.duration;
                    this.pause();
                }
            }
        } else if (!this.dirty) {
            return null;                 // paused and unchanged: the canvas is already right
        }
        const at = (this.playing && this.loop) ? this.t : Math.min(this.t, tl.duration - 1e-6);
        const out = { sample: sample(tl, at), time: Math.min(this.t, tl.duration), wrapped };
        if (!this.playing) this.dirty = false;   // drawn; the page re-marks it if the video still has to catch up
        return out;
    }
}

// Which plan step each part of a timeline belongs to: [{ n, t0, t1 }].
export function stepSpans(tl) {
    const out = [];
    for (const it of tl.items) {
        if (it.type !== "clip") continue;
        const n = tl.clips[it.clip].step, last = out[out.length - 1];
        if (last && last.n === n) last.t1 = it.t1; else out.push({ n, t0: it.t0, t1: it.t1 });
    }
    return out;
}
