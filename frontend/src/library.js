// ======================================================
// Sign library: index lookup, lazy loading, caching, and the two
// per-clip adjustments that make separately-recorded signs chain.
//
// Nothing is loaded up front except the manifest (one small JSON index
// of all 3,215 signs). A sign's motion is fetched the first time it is
// needed and kept in an LRU cache, so a sentence costs only its own signs.
// ======================================================

// ---------- decoding --------------------------------------------------
// v2 (assets/signs/motion/*.json): integer x/y per landmark, 0 = absent track.
// v1 (motion/*.json, letters + pre-stitched phrases): frames of {x,y,z}
// objects -- passed through unchanged.
export function decodeMotion(raw) {
    if (raw.v !== 2) return raw;
    const s = raw.scale || 10000;
    const pts = a => {
        if (!a) return null;
        const out = new Array(a.length / 2);
        for (let i = 0; i < out.length; i++) out[i] = { x: a[2 * i] / s, y: a[2 * i + 1] / s };
        return out;
    };
    const frames = new Array(raw.n);
    for (let i = 0; i < raw.n; i++) {
        frames[i] = { pose: pts(raw.pose[i]),
                      left_hand: pts(raw.left_hand[i]),
                      right_hand: pts(raw.right_hand[i]),
                      face: raw.face ? pts(raw.face[i]) : null };
    }
    return { fps: raw.fps, width: raw.width, height: raw.height, frames,
             faceIndices: raw.face_indices || null, src: raw.src || null };
}

export function median(values) {
    if (!values.length) return NaN;
    const v = [...values].sort((a, b) => a - b);
    const m = v.length >> 1;
    return v.length % 2 ? v[m] : (v[m - 1] + v[m]) / 2;
}

// ---------- signer normalisation --------------------------------------
// Every clip is a different recording -- different signer, distance and
// framing. Played back to back raw, the figure would jump in size and
// position at every sign boundary. Each clip is mapped by ONE similarity
// transform (uniform scale + translation, from the clip's median shoulder
// line) into a shared body frame: shoulder midpoint at the origin,
// shoulder width = 1. A single uniform transform per clip changes no
// distance ratio and no angle inside the clip, so the signing space --
// where the hands are relative to the face and body -- is preserved
// exactly; only the camera is factored out.
export function normalizeMotion(m) {
    if (m.normalized) return m;
    const aspect = m.width / m.height;
    const mx = [], my = [], sw = [];
    for (const f of m.frames) {
        const p = f.pose;
        if (!p) continue;
        mx.push((p[11].x + p[12].x) / 2 * aspect);
        my.push((p[11].y + p[12].y) / 2);
        sw.push(Math.hypot((p[11].x - p[12].x) * aspect, p[11].y - p[12].y));
    }
    if (!sw.length) return m;
    const cx = median(mx), cy = median(my), s = median(sw) || 1;
    const map = pts => pts && pts.map(q => ({ x: (q.x * aspect - cx) / s, y: (q.y - cy) / s }));
    const frames = m.frames.map(f => ({
        pose: map(f.pose), left_hand: map(f.left_hand), right_hand: map(f.right_hand),
        face: map(f.face || null) }));
    // width = height = 1: the renderer's aspect handling becomes a no-op
    return { ...m, width: 1, height: 1, frames, normalized: { cx, cy, s, aspect } };
}

// ---------- spike removal ---------------------------------------------
// MediaPipe occasionally misplaces a landmark for ONE frame and puts it
// back on the next; drawn at 60 Hz that reads as a flicker. A 3-frame
// running median per coordinate removes exactly those single-frame
// spikes and nothing else: on any steadily moving (monotonic) track the
// median of three consecutive samples IS the middle sample, so real
// motion -- including fast handshape changes -- passes through unchanged,
// and every output value is one of the three measured values (nothing is
// interpolated or invented). The cost: at a genuine turning point (a tap,
// a change of direction) the single extreme frame is clipped to its
// nearer neighbour. Applied only where a track is present in all three
// frames; the first and last frame are left alone. Library({despike:false})
// and the page's "raw tracking" switch turn it off.
const med3 = (a, b, c) => Math.max(Math.min(a, b), Math.min(Math.max(a, b), c));

export function despike(m) {
    if (m.despiked !== undefined) return m;
    const fr = m.frames;
    let changed = 0;
    const track = key => fr.map((f, i) => {
        const b = f[key];
        if (!b || i === 0 || i === fr.length - 1) return b;
        const a = fr[i - 1][key], c = fr[i + 1][key];
        if (!a || !c || a.length !== b.length || c.length !== b.length) return b;
        return b.map((p, j) => {
            const x = med3(a[j].x, p.x, c[j].x), y = med3(a[j].y, p.y, c[j].y);
            if (x !== p.x || y !== p.y) changed++;
            return { x, y };
        });
    });
    const pose = track("pose"), L = track("left_hand"), R = track("right_hand");
    const frames = fr.map((f, i) => ({ ...f, pose: pose[i], left_hand: L[i], right_hand: R[i] }));
    return { ...m, frames, despiked: changed };
}

// ---------- rest trimming ---------------------------------------------
// Each corpus clip starts and ends with the hands at rest at hip level.
// Chained raw, every sign would be bracketed by a full arms-down /
// arms-up cycle. Only LEADING and TRAILING rest is trimmed -- never
// anything between the first and last raised frame -- and only when the
// clip demonstrably starts/ends at rest:
//
//   rel   wrist height, 0 = shoulder line, 1 = hip line, per frame taking
//         the HIGHER wrist (a one-handed sign leaves the other at rest)
//   rest  the clip's first/last 3 frames must sit at rel > 0.85,
//         otherwise that end is left alone (clip cut mid-sign)
//   lift  a frame is active when it is LIFT above that rest level
//
// If the active span is under 30% of the clip, the heuristic has misread
// it (e.g. a sign made low at the waist) and the full clip is kept.
export const TRIM = { REST_MIN: 0.85, LIFT: 0.3, PAD: 2, MIN_FRACTION: 0.3 };

export function wristHeights(m) {
    return m.frames.map(f => {
        const p = f.pose;
        if (!p) return null;
        const sh = (p[11].y + p[12].y) / 2, hip = (p[23].y + p[24].y) / 2;
        if (hip - sh < 1e-6) return null;
        return (Math.min(p[15].y, p[16].y) - sh) / (hip - sh);
    });
}

export function activeSpan(m, opts = TRIM) {
    const n = m.frames.length;
    const full = [0, n - 1];
    if (n < 8) return full;
    const rel = wristHeights(m);
    const ends = idx => median(idx.map(i => rel[i]).filter(v => v !== null));
    const restStart = ends([0, 1, 2]), restEnd = ends([n - 3, n - 2, n - 1]);
    const atRestStart = restStart > opts.REST_MIN, atRestEnd = restEnd > opts.REST_MIN;
    if (!atRestStart && !atRestEnd) return full;

    const level = Math.max(atRestStart ? restStart : -Infinity, atRestEnd ? restEnd : -Infinity);
    const active = rel.map(v => v !== null && v < level - opts.LIFT);
    const first = active.indexOf(true), last = active.lastIndexOf(true);
    if (first === -1) return full;
    const s = atRestStart ? Math.max(0, first - opts.PAD) : 0;
    const e = atRestEnd ? Math.min(n - 1, last + opts.PAD) : n - 1;
    if (e - s + 1 < opts.MIN_FRACTION * n) return full;
    return [s, e];
}

// ---------- letter cores ----------------------------------------------
// The corpus letters are separate recordings: hands rise, the handshape
// is HELD, hands fall. Played whole inside a word, every letter costs 1-4 s
// (a five-letter name took ~10 s). Within a fingerspelled word only each
// letter's held part is needed: the longest run of frames where both
// wrists are still (each moving under STILL shoulder widths per frame),
// padded by PAD frames, and centre-cropped to at most MAX seconds. This
// SELECTS measured frames -- nothing is generated, re-timed or reshaped;
// the hand travel between letters is the timeline's ordinary transition.
// When no still run of MIN seconds exists, the span is left unchanged.
export const CORE = { STILL: 0.03, PAD: 2, MIN: 0.2, MAX: 0.6 };

export function letterCore(m, span, opts = CORE) {
    const [s, e] = span, fr = m.frames;
    const speed = i => {
        const a = fr[i - 1] && fr[i - 1].pose, b = fr[i] && fr[i].pose;
        if (!a || !b) return Infinity;
        return Math.max(Math.hypot(b[15].x - a[15].x, b[15].y - a[15].y),
                        Math.hypot(b[16].x - a[16].x, b[16].y - a[16].y));
    };
    let best = null, runStart = null;
    for (let i = s + 1; i <= e + 1; i++) {
        const still = i <= e && speed(i) < opts.STILL;
        if (still && runStart === null) runStart = i - 1;
        if (!still && runStart !== null) {
            if (!best || i - 1 - runStart > best[1] - best[0]) best = [runStart, i - 1];
            runStart = null;
        }
    }
    if (!best || (best[1] - best[0] + 1) / m.fps < opts.MIN) return span;
    let a = Math.max(s, best[0] - opts.PAD), b = Math.min(e, best[1] + opts.PAD);
    const max = Math.round(opts.MAX * m.fps);
    if (b - a + 1 > max) { const mid = (a + b) >> 1; a = mid - (max >> 1); b = a + max - 1; }
    return [a, b];
}

// ---------- cache -------------------------------------------------------
export class LRU {
    constructor(max) { this.max = max; this.map = new Map(); }
    get(k) {
        if (!this.map.has(k)) return undefined;
        const v = this.map.get(k);
        this.map.delete(k); this.map.set(k, v);
        return v;
    }
    set(k, v) {
        this.map.delete(k); this.map.set(k, v);
        while (this.map.size > this.max) this.map.delete(this.map.keys().next().value);
    }
    get size() { return this.map.size; }
}

// ---------- the library -------------------------------------------------
// manifest: assets/signs/manifest.json (3,215 signs, search keys)
// letters:  assets/fingerspelling/letters.json (A-Z, v1 motion files)
// phrases:  assets/signs.json entries  (pre-stitched SABIN etc., quick picks)
export class Library {
    constructor({ manifest, letters = {}, phrases = {}, keywords = null, base = ".", fetchJSON, cacheSize = 80,
                  despike: useDespike = true }) {
        this.prepareMotion = m => normalizeMotion(useDespike ? despike(m) : m);
        this.manifest = manifest || { signs: {}, keys: {}, counts: {} };
        // why an existing sign can't play: a partial web build (build_dist.py
        // --signs-from) ships only some signs and says so in its manifest
        this.unavailableText = this.manifest.unavailable_text || "not extracted yet";
        this.partial = !!this.manifest.unavailable_text;
        // English keyword -> signs, from the dataset's dictionary (scripts/build_keywords.py)
        this.keywords = (keywords && keywords.keys) || {};
        this.maxKeywordWords = Math.max(1, ...Object.keys(this.keywords).map(k => k.split(" ").length));
        this.letters = letters;
        this.phrases = phrases;
        this.base = base;
        this.fetchJSON = fetchJSON || (url => fetch(url).then(r => {
            if (!r.ok) throw new Error(`${r.status} ${url}`);
            return r.json();
        }));
        this.cache = new LRU(cacheSize);
        this.maxKeyWords = Math.max(1, ...Object.keys(this.manifest.keys)
            .map(k => k.split(" ").length));
    }

    // planner-facing lexicon
    byId(id) {
        const s = this.manifest.signs[id];
        if (!s) return null;
        return { id, gloss: s.gloss, kind: s.kind, sense: s.sense || null, keys: s.keys,
                 available: !!s.clip, low: !!s.low, q: s.q ?? null, failed: !!s.failed,
                 // from scripts/validate_signs.py: "review" | "unreliable" | null (ok)
                 status: s.status || null, flags: s.flags || [] };
    }
    candidates(key) {
        return (this.manifest.keys[key] || []).map(id => this.byId(id));
    }
    hasLetter(ch) { return !!this.letters[ch]; }
    keywordEntries(key) {
        return (this.keywords[key] || [])
            .map(([id, kind, sense, pos, n]) => ({ sign: this.byId(id), kind, sense, pos, n }))
            .filter(e => e.sign);
    }

    // ---- loading (all go through one cached path) ----
    _load(cacheKey, url, prepare) {
        let hit = this.cache.get(cacheKey);
        if (!hit) {
            hit = this.fetchJSON(url).then(raw => prepare(decodeMotion(raw)));
            hit.catch(() => this.cache.map.delete(cacheKey));   // don't cache failures
            this.cache.set(cacheKey, hit);
        }
        return hit;
    }

    sign(id) {
        const s = this.manifest.signs[id];
        if (!s || !s.clip) return Promise.reject(new Error(`sign ${id} not available`));
        return this._load(`sign:${id}`, `${this.base}/assets/signs/motion/${s.clip}.json`, m => {
            const motion = this.prepareMotion(m);
            return { kind: "sign", id, label: s.gloss, motion, span: activeSpan(motion),
                     video: `${this.base}/assets/signs/videos/${s.clip}.mp4`, low: !!s.low };
        });
    }

    letter(ch) {
        const e = this.letters[ch];
        if (!e) return Promise.reject(new Error(`no letter ${ch}`));
        return this._load(`letter:${ch}`, `${this.base}/${e.motion}`, m => {
            const motion = this.prepareMotion(m);
            const span = activeSpan(motion);
            return { kind: "letter", id: ch, label: ch, motion, span, core: letterCore(motion, span),
                     video: `${this.base}/${e.video}` };
        });
    }

    // pre-stitched phrases keep every frame: their word/letter boundaries
    // are frame indices into the full clip
    phrase(name) {
        const e = this.phrases[name];
        if (!e || !e.motion) return Promise.reject(new Error(`no phrase ${name}`));
        return this._load(`phrase:${name}`, `${this.base}/${e.motion}`, m => {
            const motion = this.prepareMotion(m);
            return { kind: "phrase", id: name, label: name, motion,
                     span: [0, motion.frames.length - 1], video: `${this.base}/${e.video}` };
        });
    }
}
