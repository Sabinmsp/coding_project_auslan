// ======================================================
// English text -> sign plan. Rule-based, deterministic, no network.
//
// This is NOT a translator. Auslan has its own grammar -- spatial
// reference, non-manual features, verb agreement -- that none of these
// rules model. What they do is the defensible minimum, each step labelled
// with the rule that produced it so a reviewer can see and undo it:
//
//   omit      articles, forms of "be", "to"/"of" are left out by the current
//             rules (a simplification, not a claim that Auslan never
//             expresses them); a person can restore any omitted word.
//   negation  "don't want" -> NOT WANT, using the corpus's own negated
//             signs where it has one; auxiliary "do" dropped.
//   phrases   longest match first, so "thank you", "next week" and
//             "credit card" are one sign each, not two.
//   stems     "paid" -> PAY, "bills" -> BILL, when the word itself has no
//             sign. Auslan marks tense with time signs, not inflection.
//   keywords  only if neither the word nor its stem names a playable sign:
//             the dataset's own English keywords for each sign
//             (assets/signs/keywords.json) -- "remember" -> RECOLLECT,
//             "can" -> ABLE, "forgot" -> FORGET. Same safety rules as the
//             gloss names. The lists are loose ("sorry" is listed for STUPID,
//             "understand" for SEE), so a keyword only plays when it is
//             STRONG: among the sign's first two keywords, or a form of the
//             sign's own name ("come" -> COMING). A loose one is spelled and
//             offered in the menu. Several strong signs: the best plays,
//             marked for review.
//   senses    a specific sense (OPEN (DOOR), CAN (TIN)) is used only if
//             the sentence contains evidence for it. With no evidence the
//             word is fingerspelled and the sense offered as an option --
//             signing "tin can" for the modal "can" would be confidently
//             wrong, which is worse than slow.
//   order     (optional) time adverbs first, wh-word last in a
//             wh-question: common Auslan patterns, applied mechanically.
//
// Anything without a sign is fingerspelled -- what a signer does for a
// name or an unknown word -- and every step says why. So is a word whose
// sign the validator marked UNRELIABLE (scripts/validate_signs.py: hands
// in the wrong slot, a hand missing for most of the sign, ...): playing a
// corrupted sign confidently is worse than spelling the word. The sign
// stays in the step's menu for a person to choose.
// ======================================================

// Words the current rules leave out. Shown as "omitted by the current
// planner" -- a choice of these rules, not a statement about Auslan.
const OMIT = {
    a: "article", an: "article", the: "article",
    am: "form of 'be'", is: "form of 'be'", are: "form of 'be'", was: "form of 'be'",
    were: "form of 'be'", be: "form of 'be'", been: "form of 'be'", being: "form of 'be'",
    to: "'to'", of: "'of'",
};
const omitted = reason => `${reason} -- omitted by the current planner`;

const CONTRACTIONS = {
    "i'm": ["i", "am"], "you're": ["you", "are"], "we're": ["we", "are"],
    "they're": ["they", "are"], "he's": ["he", "is"], "she's": ["she", "is"],
    "it's": ["it", "is"], "that's": ["that", "is"], "what's": ["what", "is"],
    "where's": ["where", "is"], "who's": ["who", "is"], "how's": ["how", "is"],
    "there's": ["there", "is"], "here's": ["here", "is"],
    "i've": ["i", "have"], "you've": ["you", "have"], "we've": ["we", "have"],
    "they've": ["they", "have"], "i'll": ["i", "will"], "you'll": ["you", "will"],
    "we'll": ["we", "will"], "they'll": ["they", "will"], "he'll": ["he", "will"],
    "she'll": ["she", "will"], "it'll": ["it", "will"], "i'd": ["i", "would"],
    "don't": ["do", "not"], "doesn't": ["does", "not"], "didn't": ["did", "not"],
    "can't": ["can", "not"], "cannot": ["can", "not"], "isn't": ["is", "not"],
    "aren't": ["are", "not"], "wasn't": ["was", "not"], "weren't": ["were", "not"],
    "haven't": ["have", "not"], "hasn't": ["has", "not"], "hadn't": ["had", "not"],
    "shouldn't": ["should", "not"], "couldn't": ["could", "not"],
    "wouldn't": ["would", "not"], "mustn't": ["must", "not"], "let's": ["let", "us"],
};

const IRREGULAR = {
    went: "go", gone: "go", goes: "go", ate: "eat", eaten: "eat", saw: "see",
    seen: "see", bought: "buy", paid: "pay", got: "get", gotten: "get",
    had: "have", has: "have", did: "do", done: "do", said: "say", told: "tell",
    made: "make", came: "come", took: "take", taken: "take", gave: "give",
    given: "give", knew: "know", known: "know", thought: "think", felt: "feel",
    left: "leave", sent: "send", spent: "spend", found: "find", wrote: "write",
    written: "write", read: "read", met: "meet", sat: "sit", stood: "stand",
    ran: "run", drove: "drive", driven: "drive", slept: "sleep", lost: "lose",
    children: "child", people: "person", men: "man", women: "woman",
    feet: "foot", teeth: "tooth", mice: "mouse", better: "good", best: "good",
    worse: "bad", worst: "bad",
};

// Time adverbs that Auslan typically places first. Dates ("10 October")
// are deliberately NOT moved: "pay by the 10th" puts the date after "by",
// and moving it would detach the deadline from what it is a deadline for.
const TIME_FIRST = new Set([
    "TODAY", "TOMORROW", "YESTERDAY", "TONIGHT", "NOW", "LATER", "SOON",
    "MORNING", "AFTERNOON", "EVENING", "NIGHT",
    "NEXT WEEK", "LAST WEEK", "THIS WEEK", "WEEK AFTER", "NEXT YEAR",
    "LAST YEAR", "THIS YEAR", "NEXT MONTH", "LAST MONTH",
]);
const WH = new Set(["WHAT", "WHO", "WHERE", "WHEN", "WHY", "HOW", "WHICH"]);

const SENSE_STOP = new Set(["THE", "A", "OF", "IN", "AT", "ON", "TO", "AND", "OR",
                            "INTO", "BY", "FOR", "SOMEONE"]);

const ONES = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight",
              "nine", "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen",
              "sixteen", "seventeen", "eighteen", "nineteen"];
const TENS = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy",
              "eighty", "ninety"];

export function numberWords(n) {
    if (n < 20) return [ONES[n]];
    if (n < 100) return n % 10 ? [TENS[Math.floor(n / 10)], ONES[n % 10]] : [TENS[n / 10]];
    if (n < 1000) {
        const rest = n % 100;
        return [ONES[Math.floor(n / 100)], "hundred", ...(rest ? numberWords(rest) : [])];
    }
    if (n < 1000000) {
        const rest = n % 1000;
        return [...numberWords(Math.floor(n / 1000)), "thousand",
                ...(rest ? numberWords(rest) : [])];
    }
    return null;
}

function numberToWords(raw) {
    const m = raw.match(/^(\d+)(st|nd|rd|th)?$/i);
    if (!m) return null;
    const n = parseInt(m[1], 10);
    // a four-digit year reads as two pairs: 2026 -> twenty twenty-six
    if (!m[2] && m[1].length === 4 && n >= 1100 && n <= 2099 && n % 100 !== 0) {
        const hi = Math.floor(n / 100), lo = n % 100;
        return { words: [...numberWords(hi), ...(lo < 10 ? ["oh", ONES[lo]] : numberWords(lo))],
                 why: `year ${raw} read as two numbers` };
    }
    const words = numberWords(n);
    return words && { words, why: `number ${raw} as words` };
}

// ------------------------------------------------------
// tokenising
// ------------------------------------------------------
export function tokenize(text) {
    const clean = text.replace(/[‘’]/g, "'");
    const out = [];
    const re = /[A-Za-z0-9]+(?:'[A-Za-z]+)*/g;
    let m, first = true;
    while ((m = re.exec(clean))) {
        const before = clean.slice(0, m.index);
        const sentenceStart = first || /[.!?]\s*$/.test(before);
        out.push({ raw: m[0], word: m[0].toLowerCase(),
                   cap: /^[A-Z]/.test(m[0]), sentenceStart, index: out.length });
        first = false;
    }
    const trimmed = clean.trim();
    return { tokens: out, question: trimmed.endsWith("?") };
}

// Expanded word list: contractions split, numbers spelled out. Each entry
// remembers which ORIGINAL token it came from, so captions can highlight
// the English the viewer typed.
// Clipped words -> the full word the corpus labels use. Same meaning, so
// the full word's sign applies; only words whose full form has a sign.
export const CLIPPED = {
    exam: "examination", exams: "examination", uni: "university", maths: "mathematics", math: "mathematics",
    tv: "television", telly: "television", fridge: "refrigerator", bike: "bicycle", bikes: "bicycle",
    gov: "government", govt: "government",
};

function expand(tokens) {
    const words = [];
    for (const t of tokens) {
        const c = CONTRACTIONS[t.word];
        if (c) { c.forEach(w => words.push({ w, src: t.index, from: t.raw, cap: false })); continue; }
        const num = numberToWords(t.word);
        if (num) {
            num.words.forEach(w => words.push({ w, src: t.index, from: t.raw, cap: false, why: num.why }));
            continue;
        }
        // possessive 's: Sabin's -> Sabin (the possession itself is not signed)
        const w = t.word.endsWith("'s") ? t.word.slice(0, -2) : t.word;
        if (CLIPPED[w]) {
            words.push({ w: CLIPPED[w], src: t.index, from: t.raw, cap: false, why: `"${w}" = "${CLIPPED[w]}"` });
            continue;
        }
        words.push({ w, src: t.index, from: t.raw, cap: t.cap && !t.sentenceStart });
    }
    return words;
}

// Base-form guesses for a word with no sign of its own. Tried in order;
// only a guess that IS a key is ever used.
export function stems(w) {
    const out = [];
    if (IRREGULAR[w]) out.push(IRREGULAR[w]);
    const add = s => { if (s.length >= 2 && s !== w && !out.includes(s)) out.push(s); };
    if (w.endsWith("ies")) add(w.slice(0, -3) + "y");
    if (w.endsWith("es")) add(w.slice(0, -2));
    if (w.endsWith("s") && !w.endsWith("ss")) add(w.slice(0, -1));
    if (w.endsWith("ied")) add(w.slice(0, -3) + "y");
    if (w.endsWith("ed")) { add(w.slice(0, -2)); add(w.slice(0, -1));
        if (/(.)\1ed$/.test(w)) add(w.slice(0, -3)); }
    if (w.endsWith("ing")) { add(w.slice(0, -3)); add(w.slice(0, -3) + "e");
        if (/(.)\1ing$/.test(w)) add(w.slice(0, -4)); }
    if (w.endsWith("ly")) add(w.slice(0, -2));
    return out;
}

const keyOf = words => words.join(" ").toUpperCase();
// A sense word that is only a form of the word being looked up ("TIMES" for
// "time") is not evidence: evidence has to come from the REST of the sentence.
const formOf = (a, b) => a === b || stems(a.toLowerCase()).includes(b.toLowerCase()) ||
                         stems(b.toLowerCase()).includes(a.toLowerCase());
// A gloss that is the word plus a DERIVATIONAL ending names the same concept
// in another word class (HAPPINESS for "happy", WHEREABOUTS for "where");
// Auslan signs often serve both. Accepted from the dictionary, but always
// marked for review. Deliberately short list: -ER is excluded (TEACHER is
// not "teach"), and so is any ending that changes the meaning.
const DERIVATIONAL = ["NESS", "MENT", "ATION", "ITY", "ABOUTS"];
// English words whose everyday meaning the derived sign does not share
// ("mean" = intend, not MEANNESS; "hard" = difficult, not HARDNESS)
const POLYSEMOUS = new Set(["MEAN", "HARD", "MAJOR", "FAIR", "PRETTY", "PLAIN", "TIGHT"]);
export const derivedFrom = (gloss, key) => {
    const k = key.toUpperCase(), roots = [k, k.replace(/E$/, ""), k.replace(/Y$/, "I")];
    return k.length >= 4 && !POLYSEMOUS.has(k) && roots.some(r => DERIVATIONAL.some(suf => gloss === r + suf));
};
const senseWordsOf = (sense, matchedKey) => (sense || "").split(" ")
    .filter(w => w && !SENSE_STOP.has(w) && !matchedKey.split(" ").some(k => formOf(w, k)));
const playable = s => !!(s && s.available && s.status !== "unreliable");

// ------------------------------------------------------
// choosing among candidate signs for one key
// ------------------------------------------------------
function chooseSign(cands, matchedKey, contextWords) {
    // the sign whose MEANING is this key: plain glosses, or a phrase gloss
    // matched on its primary key (NOT WANT matched as "not want")
    const primary = cands.filter(c => c.kind === "plain" ||
                                       (c.kind === "phrase" && c.keys[0] === matchedKey));
    const senses = cands.filter(c => !primary.includes(c));
    const senseWords = c => senseWordsOf(c.sense, matchedKey);
    const evidence = c => senseWords(c)
        .filter(w => contextWords.has(w) || stems(w.toLowerCase())
            .some(s => contextWords.has(s.toUpperCase())));
    // strongest evidence first: OPEN (DOOR) is fully supported by "door",
    // OPEN (AUTOMATIC DOORS) only half -- nothing says "automatic"
    const strength = c => evidence(c).length / Math.max(1, senseWords(c).length);
    const supported = senses.filter(c => evidence(c).length)
        .sort((a, b) => strength(b) - strength(a) ||
                        senseWords(a).length - senseWords(b).length);

    if (supported.length) {
        const c = supported[0];
        return { sign: c, match: "context", uncertain: true,
                 why: `sense "${c.sense}" chosen: the sentence mentions ` +
                      `${evidence(c).join(", ").toLowerCase()}` +
                      (cands.length > 1 ? ` (${cands.length} candidates)` : "") };
    }
    if (primary.length) {
        const c = primary[0];
        const others = cands.length - 1;
        return { sign: c, match: "exact", uncertain: false,
                 why: others ? `general sign; ${others} specific sense${others > 1 ? "s" : ""} not chosen`
                             : "exact" };
    }
    // only specific senses, none supported by the sentence
    return { sign: null, match: "sense", uncertain: true,
             why: `only specific sense${senses.length > 1 ? "s" : ""} in corpus ` +
                  `(${senses.map(c => c.sense).join(", ")}) -- no evidence in the sentence, ` +
                  `so fingerspelled` };
}

// ---- dictionary keywords ------------------------------------------------
// entries: [{sign: info, kind: "plain"|"sense"|"plural", sense, pos, n}]
function chooseKeyword(entries, matchedKey, contextWords) {
    const keyWords = matchedKey.split(" ");
    const evidence = e => senseWordsOf(e.sense, matchedKey)
        .filter(x => contextWords.has(x) || stems(x.toLowerCase())
            .some(st => contextWords.has(st.toUpperCase())));
    const direct = entries.filter(e => e.kind === "plain");
    const supported = entries.filter(e => e.kind !== "plain" && evidence(e).length);
    const pool = direct.length ? direct : supported;
    if (!pool.length) {
        return { sign: null, uncertain: true,
                 why: `the dictionary lists "${matchedKey.toLowerCase()}" only in specific senses ` +
                      `(${entries.map(e => e.sense).join(", ")}) -- no evidence in the sentence` };
    }
    // Ranked by how well each sign MEANS the word -- never by which sign
    // happens to be extracted, which would swap in a weaker sign just because
    // it is ready. First a sign whose gloss shares words with the sentence
    // ("turn on the light" -> TURN ON), then a strong listing, then the one
    // that lists this word earliest.
    const glossWords = e => e.sign.gloss.toUpperCase().split(/[^A-Z]+/).filter(Boolean);
    const overlap = e => glossWords(e).filter(x => !keyWords.includes(x) && contextWords.has(x)).length;
    const related = e => glossWords(e).some(g => keyWords.some(k => derivedFrom(g, k)));
    const strong = e => e.pos <= 1 || glossWords(e).some(g => keyWords.some(k => formOf(g, k))) || related(e);
    const ranked = [...pool].sort((a, b) =>
        (overlap(b) - overlap(a)) || (strong(b) - strong(a)) ||
        (a.pos - b.pos) || (a.pos / a.n - b.pos / b.n) ||
        (a.n - b.n) ||                       // a shorter list: the word is more central to the sign
        a.sign.id.localeCompare(b.sign.id));
    const best = ranked[0];
    if (!strong(best) && !overlap(best)) {
        return { sign: null, uncertain: true, loose: best.sign,
                 why: `the dictionary links "${matchedKey.toLowerCase()}" to ${best.sign.gloss} only loosely ` +
                      `(its keyword ${best.pos + 1} of ${best.n}) -- choose it from the menu to see it` };
    }
    const others = pool.filter(e => e !== best).map(e => e.sign.gloss);
    const onlyRelated = related(best) && best.pos > 1 && !glossWords(best).some(g => keyWords.some(k => formOf(g, k)));
    return { sign: best.sign, uncertain: others.length > 0 || pool === supported || onlyRelated,
             why: "dictionary keyword" + (onlyRelated ? `; ${best.sign.gloss} is a related form of "${matchedKey.toLowerCase()}" -- check` : "") + (others.length
                 ? `; also listed for: ${others.slice(0, 4).join(", ")}${others.length > 4 ? ", ..." : ""} -- check`
                 : pool === supported ? ` (sense "${best.sense}" fits the sentence) -- check` : "") };
}

function keywordMatch(words, i, lex, contextWords, allowStems) {
    if (!lex.keywordEntries) return null;
    const maxK = lex.maxKeywordWords || 1;
    for (let n = Math.min(maxK, words.length - i); n >= 1; n--) {
        const span = words.slice(i, i + n);
        const key = keyOf(span.map(x => x.w));
        const entries = lex.keywordEntries(key);
        if (!entries.length) continue;
        const choice = chooseKeyword(entries, key, contextWords);
        if (n > 1 && !playable(choice.sign)) continue;      // let shorter matches try
        return { n, span, key, entries, choice, stem: null };
    }
    if (allowStems) {
        for (const st of stems(words[i].w)) {
            const entries = lex.keywordEntries(st.toUpperCase());
            if (entries.length) {
                return { n: 1, span: [words[i]], key: st.toUpperCase(), entries, stem: st,
                         choice: chooseKeyword(entries, st.toUpperCase(), contextWords) };
            }
        }
    }
    return null;
}

const optionOf = o => ({ id: o.id, gloss: o.gloss, sense: o.sense, available: o.available,
                         low: o.low, status: o.status });
function mergeOptions(a, b) {
    const seen = new Set(a.map(o => o.id));
    return a.concat(b.filter(o => !seen.has(o.id) && seen.add(o.id)));
}

const NA = lex => lex.unavailableText || "not extracted yet";

function lettersOf(word) {
    return word.toUpperCase().replace(/[^A-Z]/g, "").split("");
}

// ------------------------------------------------------
// main
// ------------------------------------------------------
// lex: { candidates(KEY) -> [{id, gloss, kind, sense, keys, available, low}],
//        maxKeyWords }
export function plan(text, lex, opts = {}) {
    const auslanOrder = opts.auslanOrder !== false;
    const { tokens, question } = tokenize(text);
    const words = expand(tokens);
    const contextWords = new Set(words.map(w => w.w.toUpperCase()));
    for (const w of words) stems(w.w).forEach(s => contextWords.add(s.toUpperCase()));
    const maxN = lex.maxKeyWords || 4;

    const steps = [];
    const push = (step, from) => steps.push({
        src: [...new Set(from.map(w => w.src))],
        en: [...new Set(from.map(w => w.from))].join(" "), ...step });

    for (let i = 0; i < words.length;) {
        const w = words[i];

        // auxiliary "do" in a negation: "don't want" -> NOT WANT
        if (["do", "does", "did"].includes(w.w) && words[i + 1]?.w === "not") {
            push({ kind: "omit", why: omitted("auxiliary 'do' in a negation") }, [w]);
            i++; continue;
        }
        // do-support opening a question: "do you want ...?" -- Auslan
        // marks the question on the face, not with a sign
        if (question && i === 0 && ["do", "does", "did"].includes(w.w)) {
            push({ kind: "omit", why: omitted("'do' opening a question") }, [w]);
            i++; continue;
        }

        // longest key starting here. A multi-word key whose sign can't be
        // played (not extracted yet, or only an unsupported sense) gives way
        // to shorter matches -- "not want" with NOT WANT pending becomes
        // NOT + W-A-N-T, never one run-together fingerspelled N-O-T-W-A-N-T --
        // and the step remembers that the better sign exists.
        let hit = null, deferred = null;
        for (let n = Math.min(maxN, words.length - i); n >= 1; n--) {
            const span = words.slice(i, i + n);
            // the words as rewritten ("nineteen", "that is", "one") AND as typed
            // ("19", "that's", "one's"): labels such as COVID 19, THAT'S RIGHT and
            // USHER'S SYNDROME are written the second way
            const asTyped = keyOf(span.filter((x, k) => k === 0 || x.src !== span[k - 1].src)
                .map(x => x.from.toLowerCase().replace(/[^a-z0-9']/g, "")));
            const whole = (span[0] === words[i]) && (i === 0 || words[i - 1].src !== span[0].src) &&
                          (i + n >= words.length || words[i + n].src !== span[n - 1].src);
            let key = keyOf(span.map(x => x.w)), cands = lex.candidates(key);
            if (!cands.length && whole && asTyped !== key) { key = asTyped; cands = lex.candidates(key); }
            if (!cands.length) continue;
            if (n > 1) {
                const c = chooseSign(cands, key, contextWords);
                if (!playable(c.sign)) {
                    if (c.sign && !deferred) deferred = c.sign;
                    continue;
                }
            }
            hit = { n, span, key, cands };
            break;
        }
        const deferNote = deferred
            ? `; ${deferred.gloss} would fit better but is ${NA(lex)}` : "";

        // grammatical words Auslan does not sign -- unless they start a
        // longer phrase that IS a sign ("to do" isn't, but check anyway)
        if (OMIT[w.w] && (!hit || hit.n === 1)) {
            push({ kind: "omit", why: omitted(OMIT[w.w]) }, [w]);
            i++; continue;
        }

        let stemNote = null;
        if (!hit && !w.cap) {
            for (const s of stems(w.w)) {
                const key = s.toUpperCase();
                const cands = lex.candidates(key);
                if (cands.length) { hit = { n: 1, span: [w], key, cands }; stemNote = s; break; }
            }
        }

        // DICTIONARY KEYWORDS -- only when the gloss names (and their stems)
        // give nothing playable
        const glossChoice = hit ? chooseSign(hit.cands, hit.key, contextWords) : null;
        let kwOptions = [], kw = null;
        if (!(glossChoice && playable(glossChoice.sign))) {
            kw = keywordMatch(words, i, lex, contextWords, !w.cap);
            if (kw) kwOptions = kw.entries.map(e => optionOf(e.sign));
            if (kw && playable(kw.choice.sign)) {
                const c = kw.choice, spanWord = kw.span.map(x => x.w).join(" ");
                // standing in for an exact sign that exists but can't play is a
                // substitution -- worth a reviewer's look
                const standIn = glossChoice && glossChoice.sign;
                push({ kind: "sign", id: c.sign.id, gloss: c.sign.gloss, key: kw.key, match: "keyword",
                       uncertain: c.uncertain || !!standIn, low: !!c.sign.low || !!c.sign.status,
                       status: c.sign.status || null,
                       flags: c.sign.flags || [],
                       why: `"${spanWord}" -> ${c.sign.gloss}` +
                            (kw.stem ? ` (via "${kw.stem}")` : "") + `: ${c.why}` +
                            (standIn ? `; standing in for ${standIn.gloss}, which ` +
                                (standIn.available ? "has unreliable tracking" : `is ${NA(lex)}`) : "") +
                            (hit && !standIn ? `; not ${hit.cands.map(o => o.gloss).join(" / ")}: ` +
                                `no evidence in the sentence for that sense` : "") + deferNote,
                       options: mergeOptions(kwOptions,
                                             hit ? hit.cands.map(optionOf) : []),
                       letters: lettersOf(spanWord) }, kw.span);
                i += kw.n; continue;
            }
        }

        if (hit) {
            const c = glossChoice;
            const options = mergeOptions(hit.cands.map(optionOf), kwOptions);
            const spanWord = hit.span.map(x => x.w).join(" ");
            if (playable(c.sign)) {
                push({ kind: "sign", id: c.sign.id, gloss: c.sign.gloss, key: hit.key,
                       match: stemNote ? "stem" : c.match,
                       uncertain: c.uncertain, low: !!c.sign.low || !!c.sign.status,
                       status: c.sign.status || null,
                       flags: c.sign.flags || [],
                       why: (stemNote ? `"${w.w}" -> ${stemNote.toUpperCase()}; ` : "") +
                            (hit.span[0].why ? hit.span[0].why + "; " : "") + c.why + deferNote,
                       pending: deferred ? deferred.id : null,
                       options, letters: lettersOf(spanWord) }, hit.span);
            } else {
                const pending = c.sign && !c.sign.available;
                const unreliable = c.sign && c.sign.available && c.sign.status === "unreliable";
                push({ kind: "spell", letters: lettersOf(spanWord), key: hit.key,
                       reason: pending ? "pending" : unreliable ? "unreliable" : "sense",
                       uncertain: c.uncertain || unreliable,
                       why: (pending ? `sign ${c.sign.gloss} exists but is ${NA(lex)} -- fingerspelled`
                             : unreliable ? `sign ${c.sign.gloss} has unreliable tracking ` +
                               `(${c.sign.flags.join(", ")}) -- fingerspelled; choose it from the menu to see it`
                             : c.why) + deferNote,
                       pending: pending ? c.sign.id : (deferred ? deferred.id : null), options }, hit.span);
            }
            i += hit.n; continue;
        }

        const letters = lettersOf(w.w);
        if (letters.length) {
            const kwSign = kw && kw.choice.sign;     // listed in the dictionary, but can't play
            push({ kind: "spell", letters, options: kwOptions,
                   reason: kwSign ? (kwSign.available ? "unreliable" : "pending")
                         : kw ? "loose" : w.cap ? "name" : "nosign",
                   why: (w.why ? w.why + "; " : "") +
                        (kwSign ? `dictionary sign ${kwSign.gloss} ` +
                                  (kwSign.available ? "has unreliable tracking" : `is ${NA(lex)}`) +
                                  " -- fingerspelled"
                         : kw ? kw.choice.why + " -- fingerspelled"
                         : w.cap ? "name -- fingerspelled" : "no sign in the corpus -- fingerspelled") +
                        deferNote,
                   pending: kwSign && !kwSign.available ? kwSign.id : (deferred ? deferred.id : null) },
                 [w]);
        } else {
            push({ kind: "omit", why: omitted("no letters to sign or spell") }, [w]);
        }
        i++;
    }

    const notes = [];
    let qtype = null;
    if (question) {
        qtype = steps.some(s => s.kind === "sign" && WH.has(s.key)) ||
                steps.some(s => s.kind === "spell" && WH.has(s.letters.join(""))) ? "wh" : "yn";
        notes.push(qtype === "wh"
            ? "wh-question: in Auslan, brows are lowered throughout. The figure only shows " +
              "the face from each source clip, so this is NOT expressed."
            : "yes/no question: in Auslan, brows are raised throughout. The figure only shows " +
              "the face from each source clip, so this is NOT expressed.");
    }

    if (auslanOrder) {
        const isTime = s => s.kind === "sign" && TIME_FIRST.has(s.key);
        const time = steps.filter(isTime);
        const firstReal = steps.findIndex(s => s.kind !== "omit");
        if (time.length && !(time.length === 1 && steps.indexOf(time[0]) === firstReal)) {
            for (const s of time) { steps.splice(steps.indexOf(s), 1); s.moved = "time first"; }
            steps.unshift(...time);
        }
        if (qtype === "wh") {
            const whIdx = steps.findIndex(s => (s.kind === "sign" && WH.has(s.key)) ||
                                               (s.kind === "spell" && WH.has(s.letters.join(""))));
            const lastReal = steps.length - 1 - [...steps].reverse().findIndex(s => s.kind !== "omit");
            if (whIdx !== -1 && whIdx !== lastReal) {
                const [s] = steps.splice(whIdx, 1);
                s.moved = "wh-word last";
                steps.push(s);
            }
        }
    }

    steps.forEach((s, i) => { s.n = i; });
    return { text, tokens: tokens.map(t => t.raw), question: qtype, steps, notes,
             verified: false };
}

// ------------------------------------------------------
// gloss line: the plan as editable text, and the format an LLM (or a
// person) hands back. Sign ids, and fs:WORD for fingerspelling.
//     hello my fs:NAME fs:SABIN
// Every token is validated against the library; nothing unknown is ever
// played as a sign.
// ------------------------------------------------------
export function toGlossLine(p) {
    return p.steps.filter(s => s.kind !== "omit")
        .map(s => s.kind === "sign" ? s.id : `fs:${s.letters.join("")}`).join(" ");
}

export function fromGlossLine(line, lex) {
    const steps = [];
    const problems = [];
    for (const tok of line.trim().split(/\s+/).filter(Boolean)) {
        if (/^fs:/i.test(tok)) {
            const letters = lettersOf(tok.slice(3));
            if (letters.length) steps.push({ kind: "spell", letters, en: tok.slice(3).toLowerCase(),
                                             reason: "requested", why: "fingerspelled (gloss line)", options: [], src: [] });
            continue;
        }
        let info = lex.byId(tok.toLowerCase());
        if (!info) {
            const cands = lex.candidates(tok.toUpperCase().replace(/-/g, " "));
            info = cands.find(c => c.kind === "plain") || null;
            if (!info && cands.length) problems.push(`${tok}: only specific senses (${cands.map(c => c.id).join(", ")})`);
        }
        if (info && info.available && info.status === "unreliable") {
            problems.push(`${tok}: unreliable tracking -- fingerspelled`);
            steps.push({ kind: "spell", letters: lettersOf(info.keys[0]), en: tok.toLowerCase(),
                         reason: "unreliable", uncertain: true, src: [],
                         options: [{ id: info.id, gloss: info.gloss, sense: info.sense,
                                     available: true, low: info.low, status: info.status }],
                         why: `sign ${info.gloss} has unreliable tracking (${info.flags.join(", ")}) ` +
                              `-- fingerspelled; choose it from the menu to show it with a warning` });
        } else if (info && info.available) {
            steps.push({ kind: "sign", id: info.id, gloss: info.gloss, key: info.keys[0],
                         match: "exact", uncertain: false, low: !!info.low || !!info.status,
                         status: info.status || null,
                         flags: info.flags || [], en: tok.toLowerCase(),
                         why: "from gloss line", options: [], src: [],
                         letters: lettersOf(info.keys[0]) });
        } else {
            if (info) problems.push(`${tok}: ${NA(lex)}`);
            else if (!problems.some(p => p.startsWith(tok + ":"))) problems.push(`${tok}: no such sign`);
            const letters = lettersOf(tok);
            if (letters.length) steps.push({ kind: "spell", letters, en: tok.toLowerCase(),
                                             reason: info ? "pending" : "nosign",
                                             why: `${tok} is not a playable sign -- fingerspelled`,
                                             options: [], src: [] });
        }
    }
    steps.forEach((s, i) => { s.n = i; });
    return { text: line, tokens: [], question: null, steps, notes: problems, verified: false };
}
