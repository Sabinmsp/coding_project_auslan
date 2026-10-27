// How well does the planner use the sign library? Word by word, for a fixed
// set of everyday sentences.
//
//   node scripts/matching_report.mjs            # table + every fallback with its reason
//   node scripts/matching_report.mjs --json     # machine-readable (tests/test_matching.mjs)
//
// Each WORD of the sentence gets one outcome:
//   sign        played as a sign (also counted: "ambiguous" = the planner's
//               best guess among several meanings, shown as ⚠ Check)
//   name        fingerspelled because it is a name           (not counted)
//   omitted     left out by the planner (articles, "is"...)  (not counted)
//   spelled     fingerspelled for any other reason, with the reason
//
// coverage = signed words / (all words - names - omitted words).
// It measures how often an available sign is USED, not whether the signing
// is correct Auslan: that needs fluent signers.
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { plan } from "../frontend/src/planner.js";
import { Library } from "../frontend/src/library.js";

export const SENTENCES = [
    "My name is Sabin.", "Hello, how are you?", "I love Australia.", "Students must attend classes.",
    "I want to learn Auslan.", "Thank you for helping me.", "Please pay your bill tomorrow.",
    "Where is the hospital?", "I need help.", "Welcome to the university.",
    "I am a student.", "The doctor will see you now.", "Can you help me please?", "My friend is deaf.",
    "I live in Darwin.", "We go to school every day.", "What time is it?", "I don't understand.",
    "The bus is late today.", "Please call me tomorrow morning.", "I am happy to see you.",
    "Do you sign Auslan?", "My mother works at the hospital.", "I have a question about the exam.",
    "The library opens at nine.", "I feel sick today.", "Where is the toilet?", "Thank you very much.",
    "See you next week.", "I need to pay my rent.",
];

export function analyse(lib, sentences = SENTENCES) {
    return sentences.map(text => {
        const p = plan(text, lib);
        const words = p.tokens.map((t, i) => {
            const steps = p.steps.filter(s => (s.src || []).includes(i));
            const sign = steps.find(s => s.kind === "sign");
            const spell = steps.find(s => s.kind === "spell");
            if (sign) return { w: t, out: "sign", gloss: sign.gloss, ambiguous: !!sign.uncertain, match: sign.match };
            if (spell) return { w: t, out: spell.reason === "name" ? "name" : "spelled", reason: spell.reason, why: spell.why };
            return { w: t, out: "omitted", why: steps[0] && steps[0].why };
        });
        const n = k => words.filter(w => w.out === k).length;
        const meaningful = words.length - n("name") - n("omitted");
        return { text, words, tokens: words.length, signed: n("sign"), spelled: n("spelled"), names: n("name"),
                 omitted: n("omitted"), ambiguous: words.filter(w => w.ambiguous).length, meaningful,
                 plan: p.steps.map(s => s.kind === "sign" ? s.gloss : s.kind === "spell" ? `fs:${s.letters.join("")}` : `(${s.en})`).join(" ") };
    });
}

export function totals(rows) {
    const sum = k => rows.reduce((a, r) => a + r[k], 0);
    const t = { tokens: sum("tokens"), meaningful: sum("meaningful"), signed: sum("signed"), spelled: sum("spelled"),
                names: sum("names"), omitted: sum("omitted"), ambiguous: sum("ambiguous") };
    t.coverage = t.signed / Math.max(1, t.meaningful);
    t.confident = (t.signed - t.ambiguous) / Math.max(1, t.meaningful);
    return t;
}

if (fileURLToPath(import.meta.url) === process.argv[1]) {
    const root = new URL("../", import.meta.url);
    const readJSON = rel => JSON.parse(readFileSync(new URL(rel, root)));
    const lib = new Library({ manifest: readJSON("assets/signs/manifest.json"), keywords: readJSON("assets/signs/keywords.json") });
    const rows = analyse(lib), t = totals(rows);
    if (process.argv.includes("--json")) { console.log(JSON.stringify({ rows, totals: t }, null, 1)); process.exit(0); }
    console.log("sentence".padEnd(36), "words meaningful signed ambiguous spelled names omitted  plan");
    for (const r of rows) console.log(r.text.padEnd(36), String(r.tokens).padStart(5), String(r.meaningful).padStart(10),
        String(r.signed).padStart(6), String(r.ambiguous).padStart(9), String(r.spelled).padStart(7), String(r.names).padStart(5),
        String(r.omitted).padStart(7), "  " + r.plan);
    console.log(`\nTOTAL ${t.tokens} words, ${t.meaningful} meaningful: ${t.signed} signed (${(100 * t.coverage).toFixed(1)}%), ` +
                `of which ${t.ambiguous} ambiguous; confident ${(100 * t.confident).toFixed(1)}%; ${t.spelled} spelled; ${t.names} names; ${t.omitted} omitted`);
    console.log("\nFALLBACKS (fingerspelled, not names):");
    const seen = new Map();
    for (const r of rows) for (const w of r.words) if (w.out === "spelled") {
        const k = w.w.toLowerCase();
        if (!seen.has(k)) seen.set(k, `${w.reason}: ${w.why}`);
    }
    for (const [w, why] of [...seen].sort()) console.log(`  ${w.padEnd(12)} ${why}`);
    console.log("\nAMBIGUOUS (signed, marked ⚠ Check):");
    for (const r of rows) for (const w of r.words) if (w.ambiguous) console.log(`  ${w.w.padEnd(12)} -> ${w.gloss}`);
}
