// ======================================================
// One continuous timeline from many separately-recorded clips.
//
//   clip   frames f0..f1 of one sign, played at the clip's OWN fps and
//          timing. A display refresh (60 Hz) usually falls between two
//          recorded frames (30 fps); the figure is then drawn linearly
//          between exactly those two measurements, so motion is smooth at
//          any speed without changing its path or timing. A track present
//          in only one of the two frames is taken from the nearer frame --
//          never invented.
//   gap    a short transition from the last pose of one clip to the
//          first pose of the next. This is the only synthesised motion
//          on the timeline, and it is confined to the gap: a sign's own
//          frames are never touched. A hand present on only one side of
//          the gap is NOT interpolated (that would invent a handshape);
//          it is simply not drawn during the gap.
//
// Times are seconds of timeline time; playback speed scales the clock,
// not the timeline, so scrubbing and captions stay in timeline units.
//
// Tracking dropouts: a hand that loses tracking used to vanish in a single
// refresh and pop back a moment later -- the flicker viewers notice most.
// Now, for up to FADE recorded frames either side of a measured hand, the
// nearest measured handshape is shown FADED (alpha falls with distance)
// and carried rigidly with the arm's own measured wrist. Its shape is
// never changed and never blended with another shape; the renderer draws
// these hands translucent and without fingertip highlights, so held data
// stays visibly distinct from measured data. Beyond FADE frames the hand
// is simply not drawn, as before. The same fade replaces the hard cut in a
// transition when a hand is tracked on only one side of it.
//
// Looping wraps through one more transition (last pose -> first pose) that
// lies after `duration`, up to `loopEnd`: played only when looping, so a
// repeat never jumps.
// ======================================================

export const GAP = { word: 0.22, letter: 0.08 };
export const FADE = 6;                 // recorded frames (0.2 s at 30 fps)
const HANDS = [["left_hand", 15], ["right_hand", 16]];   // hand track, its pose wrist

export function buildTimeline(clips, gaps = GAP) {
    const items = [];
    let t = 0;
    clips.forEach((c, i) => {
        const frames = c.span[1] - c.span[0] + 1;
        const dur = frames / c.motion.fps;
        items.push({ type: "clip", clip: i, t0: t, t1: t + dur });
        t += dur;
        const next = clips[i + 1];
        if (next) {
            // letters of one fingerspelled word flow faster than separate signs
            const g = (c.kind === "letter" && next.kind === "letter" && c.step === next.step)
                ? gaps.letter : gaps.word;
            items.push({ type: "gap", from: i, to: i + 1, t0: t, t1: t + g });
            t += g;
        }
    });
    const duration = t;
    if (clips.length) {
        items.push({ type: "gap", from: clips.length - 1, to: 0, t0: t, t1: t + gaps.word, wrap: true });
        t += gaps.word;
    }
    return { clips, items, duration, loopEnd: t };
}

function lerpPts(a, b, u) {
    if (!a || !b || a.length !== b.length) return null;
    return a.map((p, i) => ({ x: p.x + (b[i].x - p.x) * u, y: p.y + (b[i].y - p.y) * u }));
}

// Between two consecutive RECORDED frames of one sign: linear, and a track
// present in only one of them comes from the nearer frame.
export function mixFrames(A, B, u) {
    const mix = (a, b) => (a && b && a.length === b.length)
        ? a.map((p, i) => ({ x: p.x + (b[i].x - p.x) * u, y: p.y + (b[i].y - p.y) * u }))
        : (u < 0.5 ? a : b) || null;
    return { pose: mix(A.pose, B.pose), left_hand: mix(A.left_hand, B.left_hand),
             right_hand: mix(A.right_hand, B.right_hand), face: mix(A.face || null, B.face || null) };
}

export function lerpFrame(A, B, u) {
    const e = u * u * (3 - 2 * u);               // smoothstep: no velocity jump at the joins
    return {
        pose: lerpPts(A.pose, B.pose, e),
        left_hand: lerpPts(A.left_hand, B.left_hand, e),
        right_hand: lerpPts(A.right_hand, B.right_hand, e),
        face: lerpPts(A.face, B.face, e),
    };
}

// The frame nearest the given end of a span that has a pose: a clip whose
// last frame lost tracking must not make the transition start from nothing.
function edgeFrame(c, atEnd) {
    const [s, e] = c.span;
    const fr = c.motion.frames;
    if (atEnd) { for (let i = e; i >= s; i--) if (fr[i].pose) return fr[i]; }
    else { for (let i = s; i <= e; i++) if (fr[i].pose) return fr[i]; }
    return fr[atEnd ? e : s];
}

// `hand` measured at a frame whose pose wrist was `from`, carried to the
// wrist position `to` (pure translation)
function carry(hand, from, to) {
    const dx = to.x - from.x, dy = to.y - from.y;
    return hand.map(p => ({ x: p.x + dx, y: p.y + dy }));
}

// Inside a clip at fractional frame `pos`: fill each missing hand from the
// nearest frame within FADE that has it, faded by distance.
function holdHands(frame, fr, span, pos, fade) {
    if (!frame.pose || fade <= 0) return frame;
    let out = frame;
    for (const [key, w] of HANDS) {
        if (frame[key]) continue;
        let best = null;
        const lo = Math.max(span[0], Math.ceil(pos - fade)), hi = Math.min(span[1], Math.floor(pos + fade));
        for (let i = lo; i <= hi; i++) {
            const f = fr[i];
            if (!f[key] || !f.pose) continue;
            const d = Math.abs(i - pos);
            if (!best || d < best.d) best = { d, f };
        }
        if (!best) continue;
        if (out === frame) out = { ...frame, held: { ...(frame.held || {}) } };
        out[key] = carry(best.f[key], best.f.pose[w], frame.pose[w]);
        out.held[key] = Math.max(0, 1 - best.d / (fade + 1));
    }
    return out;
}

function findItem(tl, t) {
    let lo = 0, hi = tl.items.length - 1;
    while (lo < hi) {
        const mid = (lo + hi + 1) >> 1;
        if (tl.items[mid].t0 <= t) lo = mid; else hi = mid - 1;
    }
    return tl.items[lo];
}

// -> { item, clip (index), local (frame index in the clip's motion, or
//      null in a gap), frame (what to draw) }
export function sample(tl, t, { fade = FADE } = {}) {
    if (!tl.items.length) return null;
    t = Math.max(0, Math.min(t, (tl.loopEnd ?? tl.duration) - 1e-9));
    const item = findItem(tl, t);
    if (item.type === "clip") {
        const c = tl.clips[item.clip];
        const pos = c.span[0] + (t - item.t0) * c.motion.fps;      // fractional frame
        const local = Math.min(c.span[1], Math.floor(pos + 1e-9));
        const u = pos - local, fr = c.motion.frames;
        const raw = (u > 1e-6 && local < c.span[1]) ? mixFrames(fr[local], fr[local + 1], u) : fr[local];
        return { item, clip: item.clip, local, frame: holdHands(raw, fr, c.span, pos, fade) };
    }
    const u = (t - item.t0) / (item.t1 - item.t0);
    const A = edgeFrame(tl.clips[item.from], true), B = edgeFrame(tl.clips[item.to], false);
    const frame = lerpFrame(A, B, u);
    // a hand on only one side: fade it out (or in) with the moving wrist
    if (fade > 0 && frame.pose) {
        const e = u * u * (3 - 2 * u);
        for (const [key, w] of HANDS) {
            if (frame[key]) continue;
            const src = A[key] && A.pose ? [A, 1 - e] : B[key] && B.pose ? [B, e] : null;
            if (!src) continue;
            frame.held = frame.held || {};
            frame[key] = carry(src[0][key], src[0].pose[w], frame.pose[w]);
            frame.held[key] = src[1];
        }
    }
    return { item, clip: item.from, local: null, frame };
}

// Every frame the timeline can show, for fitting one camera to the whole
// sentence (so the figure doesn't rescale between signs).
export function* allFrames(tl) {
    for (const c of tl.clips)
        for (let i = c.span[0]; i <= c.span[1]; i++) yield c.motion.frames[i];
}
