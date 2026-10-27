// ======================================================
// Document -> key points, offline.
//
// EXTRACTIVE: every key point is a sentence that is really in the
// document, with the page it came from. Nothing is generated, so nothing
// can be invented; the price is that points read like the document, not
// like a rewrite. (An optional AI rewrite lives in backend/summarize_llm.py;
// its output is checked against these same sentences -- see checkPoint.)
//
// Hierarchical, so a 200-page PDF costs the same as a short one per page:
//   1. pages -> sentences, with page numbers; junk removed (contents
//      lines, page furniture, fragments)
//   2. score every sentence: how informative its words are in THIS
//      document (tf-idf across pages), plus facts a student must not miss
//      (dates, times, amounts, deadlines, "must"/"required", contacts)
//   3. per chunk of pages keep the best few; from those, pick the top N
//      overall, skipping near-duplicates; present them in document order
//
// simplify() then applies plain-English substitutions ("commence" ->
// "start"). It is mechanical, it never touches a number, date or name,
// and the page labels it as rule-based.
// ======================================================

export const OPTS = { points: 10, chunkPages: 10, perChunk: 6, minWords: 6, maxWords: 45 };

const STOP = new Set(("a an the and or but if of to in on at by for with from as is are was were be been being " +
    "this that these those it its they them their there here you your we our us he she his her i me my " +
    "will would can could should may might must shall do does did not no yes so than then also about into " +
    "over under more most such any all each other some only very just which who whom whose what when where " +
    "how why has have had").split(" "));

// facts: what a summary must never alter
const FACT_RES = [
    /\b\d{1,2}(?:st|nd|rd|th)?\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?(?:\s+\d{4})?/gi,
    /\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?\s+\d{1,2}(?:st|nd|rd|th)?(?:,?\s+\d{4})?/gi,
    /\b\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}\b/g,
    /\b\d{1,2}(?::\d{2})?\s?(?:am|pm)\b/gi,
    /\$\s?\d[\d,]*(?:\.\d+)?/g,
    /\b\d+(?:\.\d+)?\s?%/g,
    /[\w.+-]+@[\w-]+\.[\w.-]+/g,
    /\bhttps?:\/\/\S+|\bwww\.\S+/gi,
    /\b\d[\d,]*(?:\.\d+)?\b/g,
];
export function factsOf(text) {
    const out = [];
    let rest = text;
    for (const re of FACT_RES) {
        rest = rest.replace(re, m => { out.push(m.trim().replace(/[.,;:]+$/, "")); return " "; });
    }
    return out;
}
const norm = s => s.toLowerCase().replace(/\s+/g, " ").replace(/[’]/g, "'");

// ---------- 1. sentences with pages ------------------------------------
const ABBR = /\b(?:e\.g|i\.e|etc|dr|mr|mrs|ms|prof|no|vol|approx|dept|st|vs|cf|fig|p|pp)\.$/i;

export function splitSentences(text) {
    const out = [];
    // a short line without end punctuation, before more text, is a heading:
    // it gets its own block instead of being glued to the next sentence
    const lines = text.split("\n");
    const marked = lines.map((l, i) => {
        const t = l.trim();
        const heading = t && i < lines.length - 1 && !/[.!?:;,]$/.test(t) &&
                        t.split(/\s+/).length <= 8 && /^[A-Z0-9]/.test(t) &&
                        /^\s*[A-Z0-9•▪◦\-–*]/.test(lines[i + 1] || "");      // a wrapped line continues in lower case
        return heading ? `\n\n${t}\n\n` : l;
    }).join("\n");
    for (const block of marked.split(/\n\s*\n|\n(?=\s*(?:[•▪◦\-–*]|\d+[.)])\s)/)) {
        const flat = block.replace(/\s*\n\s*/g, " ").replace(/\s{2,}/g, " ").trim();
        if (!flat) continue;
        let start = 0;
        const re = /[.!?](?=["')\]]?\s+["'(\[]?[A-Z0-9])/g;
        let m;
        while ((m = re.exec(flat))) {
            const piece = flat.slice(start, m.index + 1);
            if (ABBR.test(piece)) continue;
            out.push(piece.trim());
            start = m.index + 1;
        }
        const tail = flat.slice(start).trim();
        if (tail) out.push(tail);
    }
    return out.map(s => s.replace(/^[•▪◦\-–*]\s*/, "").trim()).filter(Boolean);
}

const wordsOf = s => (s.toLowerCase().match(/[a-z][a-z'-]+/g) || []);

function usable(s, o) {
    const n = wordsOf(s).length;
    if (n < o.minWords || n > o.maxWords) return false;
    if (/\.{4,}|…{2,}|(?:\s\.){3,}/.test(s)) return false;           // contents leaders
    const letters = (s.match(/[a-z]/gi) || []).length;
    if (letters / s.length < 0.55) return false;                      // tables, codes
    if (s === s.toUpperCase()) return false;                          // headings
    return true;
}

// ---------- 2. scoring ---------------------------------------------------
const MUST = /\b(must|required|requirement|mandatory|deadline|due|need to|needs to|cannot|can't|not permitted|penalt\w*|late|fail\w*|eligib\w*|apply|submit\w*|enrol\w*|attend\w*|important)\b/i;
const CONTACT = /@|\bphone\b|\bcontact\b|\bwww\.|https?:/i;

function score(sent, idf) {
    const ws = wordsOf(sent.text).filter(w => !STOP.has(w));
    if (!ws.length) return 0;
    const tf = new Map();
    for (const w of ws) tf.set(w, (tf.get(w) || 0) + 1);
    let s = 0;
    for (const [w, n] of tf) s += Math.min(n, 2) * (idf.get(w) || 0);
    s /= Math.sqrt(ws.length);
    const facts = factsOf(sent.text).length;
    if (facts) s *= 1 + Math.min(facts, 3) * 0.25;
    if (MUST.test(sent.text)) s *= 1.35;
    if (CONTACT.test(sent.text)) s *= 1.1;
    if (sent.pos === 0) s *= 1.1;                                     // opens its page
    return s;
}

const jaccard = (a, b) => {
    const A = new Set(wordsOf(a).filter(w => !STOP.has(w))), B = new Set(wordsOf(b).filter(w => !STOP.has(w)));
    let i = 0;
    for (const w of A) if (B.has(w)) i++;
    return i / Math.max(1, A.size + B.size - i);
};

// pages: [{ n, text }]  ->  { points: [{ text, simple, pages, facts, score }], stats }
export function summarize(pages, opts = {}) {
    const o = { ...OPTS, ...opts };
    const sents = [];
    for (const p of pages) {
        splitSentences(p.text || "").forEach((t, pos) => { if (usable(t, o)) sents.push({ text: t, page: p.n, pos }); });
    }
    const words = pages.reduce((a, p) => a + wordsOf(p.text || "").length, 0);
    const stats = { pages: pages.length, words, sentences: sents.length };
    if (!sents.length) return { points: [], stats };

    // idf over pages: a word on every page (the course name, "university")
    // says little; one concentrated on a few pages says a lot
    const df = new Map();
    for (const p of pages) for (const w of new Set(wordsOf(p.text || ""))) df.set(w, (df.get(w) || 0) + 1);
    const N = Math.max(1, pages.length);
    const idf = new Map([...df].map(([w, d]) => [w, Math.log(1 + N / d)]));
    for (const s of sents) s.score = score(s, idf);

    // hierarchical: best few per chunk, then the best overall. Near-
    // duplicates are skipped at BOTH levels, so a chunk that repeats what an
    // earlier one said contributes its new content instead.
    const similar = (a, b) => norm(a.text) === norm(b.text) || jaccard(a.text, b.text) > 0.5;
    const pool = [];
    const chunks = Math.ceil(N / o.chunkPages);
    const perChunk = Math.max(o.perChunk, Math.ceil(o.points * 2 / chunks));   // enough to choose from
    for (let c = 0; c * o.chunkPages < N; c++) {
        const lo = pages[c * o.chunkPages]?.n, hi = pages[Math.min(N, (c + 1) * o.chunkPages) - 1]?.n;
        let taken = 0;
        for (const s of sents.filter(s => s.page >= lo && s.page <= hi).sort((a, b) => b.score - a.score)) {
            if (taken >= perChunk) break;
            if (pool.some(p => similar(p, s))) continue;
            pool.push(s); taken++;
        }
    }
    pool.sort((a, b) => b.score - a.score);
    const chosen = pool.slice(0, o.points);
    chosen.sort((a, b) => a.page - b.page || a.pos - b.pos);
    return {
        stats,
        candidates: pool.map(s => ({ text: s.text, page: s.page })),
        points: chosen.map(s => ({ text: s.text, simple: simplify(s.text), pages: [s.page],
                                   facts: factsOf(s.text), score: +s.score.toFixed(3), source: "extract" })),
    };
}

// ---------- 3. plain English (rule-based) ---------------------------------
// Longest phrases first. Each is a standard plain-English replacement; none
// changes a fact. Not a substitute for a human editor.
const PLAIN = [
    ["in accordance with", "following"], ["with regard to", "about"], ["in relation to", "about"],
    ["in the event that", "if"], ["prior to", "before"], ["subsequent to", "after"],
    ["is required to", "must"], ["are required to", "must"], ["is obliged to", "must"], ["are obliged to", "must"],
    ["is responsible for", "must look after"], ["are responsible for", "must look after"],
    ["in order to", "to"], ["a number of", "some"], ["at this point in time", "now"],
    ["no later than", "by"], ["not later than", "by"], ["is permitted to", "can"], ["are permitted to", "can"],
    ["is not permitted", "is not allowed"], ["are not permitted", "are not allowed"],
    ["commence", "start"], ["commences", "starts"], ["commencement", "start"], ["terminate", "end"],
    ["utilise", "use"], ["utilize", "use"], ["approximately", "about"], ["sufficient", "enough"],
    ["additional", "more"], ["assistance", "help"], ["assist", "help"], ["obtain", "get"],
    ["purchase", "buy"], ["require", "need"], ["requires", "needs"], ["notify", "tell"],
    ["inform", "tell"], ["endeavour", "try"], ["facilitate", "help"], ["therefore", "so"],
    ["however", "but"], ["furthermore", "also"], ["additionally", "also"], ["whilst", "while"],
    ["regarding", "about"], ["concerning", "about"], ["remuneration", "pay"], ["participate", "take part"],
    ["examination", "exam"], ["examinations", "exams"], ["mandatory", "required"], ["submission", "hand-in"],
];
const PLAIN_RE = PLAIN.map(([a, b]) => [new RegExp(`\\b${a.replace(/ /g, "\\s+")}\\b`, "gi"), b]);

export function simplify(text) {
    let s = text;
    // drop asides in brackets -- unless they hold a fact
    s = s.replace(/\s*\(([^()]*)\)/g, (m, inner) => factsOf(inner).length ? m : "");
    for (const [re, b] of PLAIN_RE) {
        s = s.replace(re, m => m[0] === m[0].toUpperCase() && m[0] !== m[0].toLowerCase()
            ? b[0].toUpperCase() + b.slice(1) : b);
    }
    // one idea per sentence: split at semicolons
    s = s.split(/\s*;\s*/).map(x => x.trim()).filter(Boolean)
        .map(x => x[0].toUpperCase() + x.slice(1)).map(x => /[.!?]$/.test(x) ? x : x + ".").join(" ");
    return s.replace(/\s{2,}/g, " ").trim();
}

// ---------- 4. checking a point against its source --------------------------
// For AI-written points: every fact (number, date, time, amount, email,
// link) in the point must appear in the text of the pages it cites, and it
// must cite at least one real page. Returns the problems found.
export function checkPoint(point, pages) {
    const problems = [];
    const byN = new Map(pages.map(p => [p.n, p.text || ""]));
    const cited = (point.pages || []).filter(n => byN.has(n));
    if (!cited.length) problems.push("cites no page of this document");
    const src = norm(cited.map(n => byN.get(n)).join(" "));
    for (const f of factsOf(point.simple || point.text || "")) {
        if (!src.includes(norm(f))) problems.push(`"${f}" is not on the cited page${cited.length > 1 ? "s" : ""}`);
    }
    return problems;
}
