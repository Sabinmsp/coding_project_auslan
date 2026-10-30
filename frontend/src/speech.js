// ======================================================
// Voice input: speech -> English text. Nothing else.
//
// Wraps the browser's Web Speech API (SpeechRecognition; webkit-prefixed
// in Chrome, Edge and Safari; absent in Firefox). It knows nothing about
// signs: the page hands the final transcript to the same planner that
// typed text goes through, so voice and typing can never disagree.
//
//   one utterance per press   continuous = false: the browser stops by
//                             itself after a pause, so the microphone is
//                             never left on
//   interim results           shown live as a subtitle while speaking
//   final transcript          onFinal(text) once; if the browser ends
//                             without marking a result final (Safari can),
//                             the last interim text is used
//   errors                    turned into plain sentences (describeError)
//
// PRIVACY: SignBridge never records, stores or uploads audio itself. The
// browser's speech service does the recognition and, depending on the
// browser, may send the audio to its vendor's servers (Google for Chrome,
// Apple for Safari). The page says so next to the microphone button.
//
// `Recognition` is injectable: tests drive a fake one.
// ======================================================

export function getRecognition(win = globalThis) {
    return win.SpeechRecognition || win.webkitSpeechRecognition || null;
}

// The error codes of the Web Speech API, in words a user can act on.
// "aborted" (we stopped it ourselves) is not an error: null.
export function describeError(code) {
    switch (code) {
        case "aborted": return null;
        case "not-allowed":
        case "service-not-allowed":
            return "Microphone access was blocked. Allow the microphone for this site in the browser's address bar, or type instead.";
        case "no-speech": return "No speech was heard. Press Speak and try again, a little closer to the microphone.";
        case "audio-capture": return "No microphone was found. Connect one, or type instead.";
        case "network": return "Speech recognition needs an internet connection in this browser. Type instead, or try again.";
        case "language-not-supported": return "This browser can't recognise Australian English. Type instead.";
        default: return "Voice input stopped unexpectedly. Try again, or type instead.";
    }
}

export class Listener {
    constructor({ Recognition = getRecognition(), lang = "en-AU",
                  onInterim = () => {}, onFinal = () => {}, onState = () => {}, onError = () => {} } = {}) {
        this.Recognition = Recognition;
        this.lang = lang;
        Object.assign(this, { onInterim, onFinal, onState, onError });
        this.state = "idle";         // idle | listening
        this.rec = null;
    }

    get supported() { return !!this.Recognition; }

    _set(state) {
        if (this.state === state) return;
        this.state = state;
        this.onState(state);
    }

    start() {
        if (!this.supported) { this.onError("unsupported", "Voice input isn't available in this browser. Use Chrome, Edge or Safari, or type instead."); return false; }
        if (this.state !== "idle") return false;           // a second press while listening is ignored
        const rec = new this.Recognition();
        rec.lang = this.lang;
        rec.continuous = false;
        rec.interimResults = true;
        rec.maxAlternatives = 1;
        let finalText = "", interim = "", failed = false, delivered = false;

        rec.onresult = e => {
            // e.results holds the whole session so far: rebuild both parts each time
            finalText = ""; interim = "";
            for (let i = 0; i < e.results.length; i++) {
                const r = e.results[i], text = r[0] ? r[0].transcript : "";
                if (r.isFinal) finalText += text + " "; else interim += text + " ";
            }
            const shown = (finalText + " " + interim).replace(/\s+/g, " ").trim();
            if (shown) this.onInterim(shown);
        };
        rec.onerror = e => {
            const msg = describeError(e.error);
            if (msg) { failed = true; this.onError(e.error, msg); }
        };
        rec.onend = () => {
            if (this.rec !== rec) return;                   // a stale session
            this.rec = null;
            this._set("idle");
            if (failed || delivered) return;
            const text = (finalText || interim).replace(/\s+/g, " ").trim();
            delivered = true;
            if (text) this.onFinal(text);
            else this.onError("no-speech", describeError("no-speech"));
        };

        this.rec = rec;
        try {
            rec.start();
        } catch (err) {                                     // e.g. InvalidStateError
            this.rec = null;
            this.onError("start-failed", describeError("start-failed"));
            return false;
        }
        this._set("listening");
        return true;
    }

    // Stop listening; whatever was heard so far is still delivered (onend).
    stop() { if (this.rec) this.rec.stop(); }

    // Stop and throw away what was heard.
    cancel() {
        const rec = this.rec;
        if (!rec) return;
        this.rec = null;
        try { rec.abort(); } catch { /* already ended */ }
        this._set("idle");
    }

    toggle() { return this.state === "idle" ? this.start() : (this.stop(), false); }
}

// A transcript as a sentence: speech services return lower case without
// punctuation ("my name is sabin"). Only the first letter is capitalised;
// nothing is guessed (no full stop or question mark is added, names are
// not detected).
export function asSentence(text) {
    const t = text.replace(/\s+/g, " ").trim();
    if (!t) return t;
    return t[0].toUpperCase() + t.slice(1);
}
