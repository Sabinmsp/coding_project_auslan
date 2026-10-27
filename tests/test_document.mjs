// node --test tests/
// Document pipeline: PDF text clean-up, the offline summariser, plain-English
// rules, and the fact check applied to AI-written points.
import { test } from "node:test";
import assert from "node:assert/strict";
import { cleanPages } from "../frontend/src/document.js";
import { summarize, simplify, factsOf, checkPoint, splitSentences } from "../frontend/src/summarize.js";

const HANDBOOK = [
    { n: 1, text: "Welcome\nWelcome to the university. This handbook explains what you need to know in your first year.\n" +
        "Enrolment\nYou must complete your enrolment online no later than 14 February 2027.\n" +
        "If you need assistance with enrolment, contact Student Central on 08 8946 0000 or at studentcentral@example.edu." },
    { n: 2, text: "Assessment\nAssignments are required to be submitted through the learning portal by 11:59 pm on the due date.\n" +
        "Late assignments lose 5% of the available marks for each day they are late.\n" +
        "Contents ........................................ 4" },
    { n: 3, text: "Examinations\nThe final examination period commences on 2 June 2027 and ends on 13 June 2027.\n" +
        "Bring your student card to every examination; you cannot enter the room without it.\n" +
        "Your tuition fees are due on 31 March 2027 (see the fees page)." },
];

test("summary: every point is a real sentence with its page, in document order", () => {
    const { points, stats } = summarize(HANDBOOK, { points: 5 });
    assert.equal(stats.pages, 3);
    assert.ok(points.length > 0 && points.length <= 5);
    const pagesInOrder = points.map(p => p.pages[0]);
    assert.deepEqual(pagesInOrder, [...pagesInOrder].sort((a, b) => a - b));
    for (const p of points) {
        const src = HANDBOOK.find(h => h.n === p.pages[0]).text.replace(/\s*\n\s*/g, " ");
        assert.ok(src.includes(p.text), `"${p.text}" is on page ${p.pages[0]}`);
    }
});

test("summary: facts survive simplification exactly", () => {
    for (const p of summarize(HANDBOOK, { points: 10 }).points) {
        assert.deepEqual(factsOf(p.simple).sort(), factsOf(p.text).sort(), p.text);
    }
});

test("summary: dates, deadlines and contacts are preferred", () => {
    for (const p of summarize(HANDBOOK, { points: 4 }).points) {
        assert.ok(p.facts.length || /\b(must|required|due|cannot)\b/i.test(p.text), `a fact or an obligation: ${p.text}`);
    }
});

test("summary: contents lines, headings and fragments are never points", () => {
    for (const p of summarize(HANDBOOK, { points: 20 }).points) {
        assert.doesNotMatch(p.text, /\.{4,}/);
        assert.notEqual(p.text, "Welcome");
        assert.ok(!/^(Enrolment|Assessment|Examinations) /.test(p.text), `heading glued on: ${p.text}`);
    }
});

test("summary: empty or text-free documents give no points, without throwing", () => {
    assert.equal(summarize([]).points.length, 0);
    assert.equal(summarize([{ n: 1, text: "" }, { n: 2, text: "   " }]).points.length, 0);
});

test("summary: duplicate sentences on many pages appear once", () => {
    const pages = Array.from({ length: 12 }, (_, i) => ({ n: i + 1,
        text: `Academic integrity means that the work you submit must be your own.\nUnit ${i} meets on Monday at 10 am in room ${i + 100}.` }));
    const texts = summarize(pages, { points: 10 }).points.map(p => p.text);
    assert.equal(texts.filter(t => t.startsWith("Academic integrity")).length, 1);
});

test("summary: hierarchical -- a 200-page document is fast and draws from across it", () => {
    const SENT = [
        d => `Library loans must be returned within ${d} days or a fine applies.`,
        d => `Parking permits cost $${d * 10} per semester and are sold at the front desk.`,
        d => `Scholarship applications close on ${d} March 2027 and late forms are not accepted.`,
        d => `On-campus housing offers are emailed to students before ${d} January 2027.`,
        d => `Placement students need a police check at least ${d} weeks before starting.`,
        d => `Graduation gowns can be hired from the bookshop for $${d * 5}.`,
        d => `Laboratory safety training is compulsory and runs every Monday at ${1 + d % 11} am.`,
        d => `Counselling appointments are free and can be booked up to ${d} days ahead.`,
        d => `The careers fair is held in the main hall on ${d} August 2027.`,
        d => `Childcare places are limited, so families should apply ${d} months early.`,
    ];
    const pages = Array.from({ length: 200 }, (_, i) => ({ n: i + 1, text:
        `Section ${i + 1}\n${SENT[Math.floor(i / 20)](2 + i % 25)}\n` +
        "General information about the campus and its facilities is available online for everyone." }));
    const t = performance.now();
    const { points } = summarize(pages);
    assert.ok(performance.now() - t < 2000, "under 2 s");
    assert.equal(points.length, 10);
    assert.ok(new Set(points.map(p => Math.ceil(p.pages[0] / 50))).size > 1, "points from more than one part");
});

test("plain English: standard substitutions, brackets without facts dropped, facts untouched", () => {
    assert.equal(simplify("Assignments are required to be submitted prior to 5 pm."), "Assignments must be submitted before 5 pm.");
    assert.equal(simplify("The examination commences tomorrow (as usual)."), "The exam starts tomorrow.");
    assert.equal(simplify("Fees are due (on 31 March 2027)."), "Fees are due (on 31 March 2027).");
    assert.equal(simplify("Bring your card; you cannot enter without it."), "Bring your card. You cannot enter without it.");
});

test("sentence splitting keeps abbreviations and splits bullets", () => {
    assert.deepEqual(splitSentences("See Dr. Smith, e.g. on Monday. Then leave."), ["See Dr. Smith, e.g. on Monday.", "Then leave."]);
    assert.deepEqual(splitSentences("Bring:\n• your card\n• a pen"), ["Bring:", "your card", "a pen"]);
});

test("PDF clean-up: running header/footer and page numbers removed, hyphens rejoined, body kept", () => {
    const pages = Array.from({ length: 6 }, (_, i) => ({ n: i + 1, lines: [
        "Example University Student Handbook 2027",
        `Unit ${"ABCDEF"[i]} has an exam-`, "ination at the end.",
        "Academic integrity means that the work you submit must be your own and properly referenced.",
        `Page ${i + 1}`] }));
    const out = cleanPages(pages);
    for (const p of out) {
        assert.ok(!p.text.includes("Student Handbook 2027"), "header removed");
        assert.ok(!/Page \d/.test(p.text), "page number removed");
        assert.ok(p.text.includes("examination at the end."), "hyphenated word rejoined");
        assert.ok(p.text.includes("Academic integrity"), "repeated BODY text kept");
    }
    // a short document has no furniture to detect
    assert.ok(cleanPages(pages.slice(0, 2))[0].text.includes("Student Handbook"));
});

test("fact check: AI points must cite real pages and copy facts exactly", () => {
    assert.deepEqual(checkPoint({ simple: "Fees are due on 31 March 2027.", pages: [3] }, HANDBOOK), []);
    const wrongDate = checkPoint({ simple: "Fees are due on 30 March 2027.", pages: [3] }, HANDBOOK);
    assert.ok(wrongDate.some(p => p.includes("30 March 2027")), wrongDate.join("; "));
    const wrongPage = checkPoint({ simple: "Fees are due on 31 March 2027.", pages: [1] }, HANDBOOK);
    assert.ok(wrongPage.length, "the fact is not on the page it cites");
    assert.ok(checkPoint({ simple: "Fees are due.", pages: [99] }, HANDBOOK).some(p => p.includes("cites no page")));
});
