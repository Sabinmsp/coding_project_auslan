// ======================================================
// 2D avatar renderer: motion frame -> canvas. Nothing else.
//
// No network, no playback state, no page elements: give it a canvas and a
// frame and it draws. The drawing is deliberately literal. Landmarks are
// already in image space, which is the space a 2D figure lives in, so they
// are drawn as measured:
//   - nothing is smoothed or invented here (spike removal and held hands
//     happen earlier, in library.js and timeline.js, and are labelled)
//   - a hand that is held (tracking lost) is drawn faded, without highlights
//   - the figure carries x, y only: the motion files hold no depth, so hand
//     orientation toward or away from the camera cannot be drawn
// ======================================================
// ---- MediaPipe topology -------------------------------------------
const POSE = {
    NOSE: 0, L_EYE: 2, R_EYE: 5,
    L_SHOULDER: 11, R_SHOULDER: 12, L_ELBOW: 13, R_ELBOW: 14,
    L_WRIST: 15, R_WRIST: 16, L_HIP: 23, R_HIP: 24
};
const PALM = [0, 1, 5, 9, 13, 17];          // wrist, thumb base, finger bases
const TIPS = [4, 8, 12, 16, 20];
const HAND_LINKS = [
    [0,1],[1,2],[2,3],[3,4],
    [0,5],[5,6],[6,7],[7,8],
    [0,9],[9,10],[10,11],[11,12],
    [0,13],[13,14],[14,15],[15,16],
    [0,17],[17,18],[18,19],[19,20],
    [5,9],[9,13],[13,17]
];

// ======================================================
// LAYOUT
//
// Computed once per sign from the whole clip, not per frame: fitting to
// each frame's own extent would make the figure breathe as the arms
// move. One transform for the clip keeps it still.
// ======================================================
export function computeLayout(motion) {
    const aspect = motion.width / motion.height;
    let minX = 1e9, maxX = -1e9, minY = 1e9, maxY = -1e9;

    const see = (x, y) => {
        minX = Math.min(minX, x); maxX = Math.max(maxX, x);
        minY = Math.min(minY, y); maxY = Math.max(maxY, y);
    };

    for (const frame of motion.frames) {
        const p = frame.pose;
        if (!p) continue;
        for (const i of [POSE.NOSE, POSE.L_SHOULDER, POSE.R_SHOULDER,
                         POSE.L_ELBOW, POSE.R_ELBOW, POSE.L_WRIST, POSE.R_WRIST,
                         POSE.L_HIP, POSE.R_HIP]) {
            see(p[i].x * aspect, p[i].y);
        }
        for (const key of ["left_hand", "right_hand"]) {
            const h = frame[key];
            if (!h) continue;
            for (const lm of h) see(lm.x * aspect, lm.y);
        }
        if (frame.face) for (const lm of frame.face) see(lm.x * aspect, lm.y);
    }
    // Centre on the BODY, not on the full extent. A raised arm reaches
    // further to one side than the other, and centring on that pushes
    // the figure off to the opposite side of the frame. The box is
    // widened symmetrically about the torso instead, so the signer stays
    // put and the arm still fits.
    let cx = 0, n = 0;
    for (const frame of motion.frames) {
        const p = frame.pose;
        if (!p) continue;
        cx += (p[POSE.L_SHOULDER].x + p[POSE.R_SHOULDER].x +
               p[POSE.L_HIP].x + p[POSE.R_HIP].x) / 4 * aspect;
        n++;
    }
    cx = n ? cx / n : (minX + maxX) / 2;

    const half = Math.max(maxX - cx, cx - minX) * 1.16 + 0.04;
    const padTop = (maxY - minY) * 0.28 + 0.04;
    const padBottom = (maxY - minY) * 0.10 + 0.03;
    return { aspect,
             minX: cx - half, maxX: cx + half,
             minY: minY - padTop, maxY: maxY + padBottom };
}

export function project(x, y, layout, W, H) {
    const boxW = layout.maxX - layout.minX;
    const boxH = layout.maxY - layout.minY;
    const scale = Math.min(W / boxW, H / boxH);
    const offX = (W - boxW * scale) / 2;
    const offY = (H - boxH * scale) / 2;
    return [offX + (x * layout.aspect - layout.minX) * scale,
            offY + (y - layout.minY) * scale];
}


// Colours only; the page passes its own (index.html --fig-* tokens).
const DEFAULT_THEME = { body: "#334155", fill: "#E2E8F0", right: "#2563EB", left: "#EA580C",
                        head: "#FFFFFF", face: "#334155", lips: "#E11D48" };

export function createRenderer(canvas) {
    const ctx = canvas.getContext("2d");
    let faceTopo = null;       // assets/signs/face_topology.json
    let showFace = false;      // face landmarks from the recording, or a plain head outline
    let theme = { ...DEFAULT_THEME };

    function limb(a, b, width, colour) {
        ctx.strokeStyle = colour;
        ctx.lineWidth = width;
        ctx.beginPath();
        ctx.moveTo(a[0], a[1]);
        ctx.lineTo(b[0], b[1]);
        ctx.stroke();
    }

    // shoulder -> elbow -> wrist as ONE stroke: the elbow is a round joint,
    // not two overlapping line ends
    function arm(points, width, colour) {
        ctx.strokeStyle = colour;
        ctx.lineWidth = width;
        ctx.beginPath();
        ctx.moveTo(points[0][0], points[0][1]);
        for (const q of points.slice(1)) ctx.lineTo(q[0], q[1]);
        ctx.stroke();
    }

    function dot(p, r, colour) {
        ctx.fillStyle = colour;
        ctx.beginPath();
        ctx.arc(p[0], p[1], r, 0, Math.PI * 2);
        ctx.fill();
    }

    function drawFrame(frame, layout) {
        const W = canvas.width, H = canvas.height;
        ctx.clearRect(0, 0, W, H);
        if (!frame || !frame.pose) return;

        const p = frame.pose;
        const P = i => project(p[i].x, p[i].y, layout, W, H);
        const unit = Math.min(W, H);
        // Line widths follow the FIGURE's size on screen (the layout box), not
        // the canvas's: the figure looks the same in a wide viewer, on a tall
        // phone and in full screen.
        const boxScale = Math.min(W / (layout.maxX - layout.minX), H / (layout.maxY - layout.minY));
        const thick = Math.max(2, (layout.maxY - layout.minY) * boxScale * 0.021);
        ctx.lineCap = "round";
        ctx.lineJoin = "round";

        // ---- torso as a filled shape, so the figure reads as a body -----
        const ls = P(POSE.L_SHOULDER), rs = P(POSE.R_SHOULDER);
        const lh = P(POSE.L_HIP), rh = P(POSE.R_HIP);
        ctx.beginPath();
        ctx.moveTo(ls[0], ls[1]); ctx.lineTo(rs[0], rs[1]);
        ctx.lineTo(rh[0], rh[1]); ctx.lineTo(lh[0], lh[1]);
        ctx.closePath();
        ctx.fillStyle = theme.fill; ctx.fill();
        ctx.strokeStyle = theme.body; ctx.lineWidth = thick * 0.8; ctx.stroke();
        // The pose model and the hand model each estimate the wrist. Drawing the
        // forearm to one and the hand from the other left a visible gap, so
        // when a hand is present and attached (its wrist within 0.35 shoulder
        // widths of the arm's), the forearm ends at the hand's own wrist point.
        // Both are measurements; this only picks the one arm and hand share.
        const swPx = Math.hypot(ls[0] - rs[0], ls[1] - rs[1]) || 1;
        const wristFor = (key, wristIndex) => {
            const h = frame[key], w = P(wristIndex);
            if (!h || h.length !== 21) return w;
            const root = project(h[0].x, h[0].y, layout, W, H);
            return Math.hypot(root[0] - w[0], root[1] - w[1]) <= 0.35 * swPx ? root : w;
        };
        const wristL = wristFor("left_hand", POSE.L_WRIST), wristR = wristFor("right_hand", POSE.R_WRIST);
        arm([P(POSE.L_SHOULDER), P(POSE.L_ELBOW), wristL], thick, theme.left);
        arm([P(POSE.R_SHOULDER), P(POSE.R_ELBOW), wristR], thick, theme.right);

        // ---- head ------------------------------------------------------
        const nose = P(POSE.NOSE);
        const neck = [(ls[0] + rs[0]) / 2, (ls[1] + rs[1]) / 2];
        // 0.49 x nose-neck: the median face-outline radius measured over the
        // sign library, so a head without face landmarks (letters) is the same
        // size as one with them
        const headR = Math.max(unit * 0.02, Math.hypot(nose[0] - neck[0], nose[1] - neck[1]) * 0.49);
        limb(neck, nose, thick * 0.7, theme.body);
        if (frame.face && faceTopo && showFace) {
            drawFace(frame.face, layout, W, H, thick);
        } else {
            ctx.fillStyle = theme.head;
            ctx.strokeStyle = theme.body;
            ctx.lineWidth = thick * 0.55;
            ctx.beginPath();
            ctx.arc(nose[0], nose[1], headR, 0, Math.PI * 2);
            ctx.fill(); ctx.stroke();
        }

        // ---- hands -----------------------------------------------------
        // Every finger joint the tracker measured is drawn; the bones are one
        // path per hand, so joints are round and a translucent (held) hand has
        // no darker blots where segments overlap. The palm (wrist + the base
        // of each finger) is tinted so the hand reads as a hand -- a fill
        // between measured points, adding no position the data does not have.
        for (const [key, colour, wrist] of [["left_hand", theme.left, wristL], ["right_hand", theme.right, wristR]]) {
            const h = frame[key];
            if (!h || h.length !== 21) {
                dot(wrist, thick * 0.6, colour);
                continue;
            }
            const q = h.map(lm => project(lm.x, lm.y, layout, W, H));
            // a HELD hand (tracking lost for a moment, see timeline.js) is drawn
            // translucent and without fingertip highlights: visibly not measured
            const held = frame.held && frame.held[key] !== undefined ? frame.held[key] : null;
            const alpha = held !== null ? 0.65 * held : 1;
            ctx.globalAlpha = alpha * 0.28;          // palm tint: reads as a hand at a glance
            ctx.fillStyle = colour;
            ctx.beginPath();
            PALM.forEach((i, k) => k ? ctx.lineTo(q[i][0], q[i][1]) : ctx.moveTo(q[i][0], q[i][1]));
            ctx.closePath(); ctx.fill();
            ctx.globalAlpha = alpha;
            ctx.strokeStyle = colour;
            ctx.lineWidth = thick * 0.52;            // fingers: thick enough to follow on a phone
            ctx.beginPath();
            for (const [a, b] of HAND_LINKS) { ctx.moveTo(q[a][0], q[a][1]); ctx.lineTo(q[b][0], q[b][1]); }
            ctx.stroke();
            if (held === null) {
                // fingertips: a light centre ringed in the hand's colour, easy to follow
                ctx.lineWidth = thick * 0.16;
                for (const i of TIPS) {
                    ctx.beginPath();
                    ctx.arc(q[i][0], q[i][1], thick * 0.3, 0, Math.PI * 2);
                    ctx.fillStyle = theme.head; ctx.fill(); ctx.stroke();
                }
            }
            ctx.globalAlpha = 1;
        }
    }


    // The face from the source clip's own landmarks: outline, brows, eyes,
    // lips. Brow position and mouth shape carry grammar in Auslan; a circle
    // for a head shows none of it. Drawn only where the clip has a tracked
    // face -- letters and the pre-stitched phrases fall back to the circle.
    function drawFace(face, layout, W, H, thick) {
        const F = i => project(face[i].x, face[i].y, layout, W, H);
        ctx.fillStyle = theme.head;
        ctx.strokeStyle = theme.body;
        ctx.lineWidth = thick * 0.45;
        ctx.beginPath();
        faceTopo.oval_loop.forEach((i, k) => {
            const p = F(i);
            if (k) ctx.lineTo(p[0], p[1]); else ctx.moveTo(p[0], p[1]);
        });
        ctx.closePath(); ctx.fill(); ctx.stroke();

        const lines = (edges, width, colour) => {
            ctx.strokeStyle = colour; ctx.lineWidth = width; ctx.lineCap = "round";
            ctx.beginPath();
            for (const [a, b] of edges) {
                const p = F(a), q = F(b);
                ctx.moveTo(p[0], p[1]); ctx.lineTo(q[0], q[1]);
            }
            ctx.stroke();
        };
        const parts = faceTopo.parts;
        lines(parts.left_eyebrow, thick * 0.3, theme.face);
        lines(parts.right_eyebrow, thick * 0.3, theme.face);
        lines(parts.left_eye, thick * 0.16, theme.face);
        lines(parts.right_eye, thick * 0.16, theme.face);
        lines(parts.lips, thick * 0.2, theme.lips);
    }


    return {
        drawFrame,
        clear() { ctx.clearRect(0, 0, canvas.width, canvas.height); },
        setFaceTopology(t) { faceTopo = t; },
        setShowFace(v) { showFace = !!v; },
        // colours only; an empty value keeps the default
        setTheme(t) { for (const [k, v] of Object.entries(t || {})) if (v) theme[k] = v; },
    };
}
