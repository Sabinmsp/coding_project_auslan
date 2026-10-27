// ======================================================
// PDF -> pages of text, in the browser.
//
// The file never leaves the viewer's computer: pdf.js (vendor/pdfjs,
// Mozilla, Apache-2.0) reads it locally, page by page, so a 200-page
// handbook needs no upload limit and works offline. pdf.js is loaded only
// when a PDF is first opened.
//
// Clean-up, all mechanical:
//   - lines rebuilt from pdf.js text items (it reports end-of-line)
//   - words split across lines by a hyphen rejoined ("exam-" + "ination")
//   - page furniture removed: a line that repeats on many pages (running
//     header/footer) and lines that are only a page number
// ======================================================

let loading = null;
function loadPdfJs(base) {
    if (window.pdfjsLib) return Promise.resolve(window.pdfjsLib);
    loading ??= new Promise((resolve, reject) => {
        const s = document.createElement("script");
        s.src = `${base}/vendor/pdfjs/pdf.min.js`;
        s.onload = () => {
            window.pdfjsLib.GlobalWorkerOptions.workerSrc = `${base}/vendor/pdfjs/pdf.worker.min.js`;
            resolve(window.pdfjsLib);
        };
        s.onerror = () => { loading = null; reject(new Error("could not load the PDF reader (vendor/pdfjs)")); };
        document.head.appendChild(s);
    });
    return loading;
}

export const LIMITS = { bytes: 60e6, pages: 500 };

// file: a File/Blob. onProgress(done, total). Throws Error with a message
// fit to show the viewer.
export async function readPdf(file, { onProgress = () => {}, base = ".", signal } = {}) {
    if (!file) throw new Error("No file chosen.");
    if (file.size > LIMITS.bytes) throw new Error(`This PDF is ${(file.size / 1e6).toFixed(0)} MB; the limit is ${LIMITS.bytes / 1e6} MB.`);
    const head = new Uint8Array(await file.slice(0, 1024).arrayBuffer());
    if (!String.fromCharCode(...head).includes("%PDF-")) throw new Error("This file is not a PDF.");
    const pdfjs = await loadPdfJs(base);
    let doc;
    try {
        doc = await pdfjs.getDocument({ data: new Uint8Array(await file.arrayBuffer()) }).promise;
    } catch (e) {
        if (e && e.name === "PasswordException") throw new Error("This PDF is password-protected.");
        throw new Error("This PDF could not be read (it may be damaged).");
    }
    const total = Math.min(doc.numPages, LIMITS.pages);
    const pages = [];
    for (let n = 1; n <= total; n++) {
        if (signal && signal.aborted) throw new Error("Cancelled.");
        const page = await doc.getPage(n);
        const tc = await page.getTextContent();
        let line = "", lines = [];
        for (const it of tc.items) {
            line += it.str;
            if (it.hasEOL) { lines.push(line); line = ""; }
            else if (it.str && !/\s$/.test(it.str)) line += " ";
        }
        if (line) lines.push(line);
        pages.push({ n, lines: lines.map(l => l.replace(/\s+/g, " ").trim()) });
        page.cleanup();
        onProgress(n, total);
    }
    const meta = await doc.getMetadata().catch(() => null);
    const title = (meta && meta.info && meta.info.Title) || file.name.replace(/\.pdf$/i, "");
    await doc.destroy();
    return { title, numPages: doc.numPages, truncated: doc.numPages > total, pages: cleanPages(pages) };
}

// pages: [{ n, lines }] -> [{ n, text }]   (pure; tested in Node)
export function cleanPages(pages) {
    // furniture = a SHORT line in a page's first or last EDGE lines that
    // repeats on many pages. Body text that happens to repeat (boilerplate
    // in every unit guide) is kept: it is content, and dedup handles it.
    const EDGE = 2;
    const key = l => l.toLowerCase().replace(/\d+/g, "#").trim();
    const edge = (p, i) => i < EDGE || i >= p.lines.length - EDGE;
    const short = l => l.split(/\s+/).length <= 12;
    const seen = new Map();
    for (const p of pages) {
        const ks = new Set(p.lines.filter((l, i) => edge(p, i) && short(l)).map(key));
        for (const k of ks) if (k) seen.set(k, (seen.get(k) || 0) + 1);
    }
    const furniture = (p, i) => pages.length >= 4 && edge(p, i) && short(p.lines[i]) &&
        seen.get(key(p.lines[i])) >= Math.max(3, pages.length * 0.3);
    return pages.map(p => {
        const kept = p.lines.filter((l, i) => l && !/^(?:page\s*)?\d+(?:\s*(?:of|\/)\s*\d+)?$/i.test(l) && !furniture(p, i));
        let text = "";
        for (const l of kept) {
            if (/[a-z]-$/.test(text) && /^[a-z]/.test(l)) text = text.slice(0, -1) + l;   // de-hyphenate
            else text += (text ? "\n" : "") + l;
        }
        return { n: p.n, text };
    });
}
