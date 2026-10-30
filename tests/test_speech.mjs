// Voice input (frontend/src/speech.js) with a fake recognition engine:
// no microphone, no browser.   node --test tests/test_speech.mjs
import { test } from "node:test";
import assert from "node:assert/strict";
import { Listener, describeError, asSentence, getRecognition } from "../frontend/src/speech.js";

// A stand-in for SpeechRecognition: the test says what the "browser" hears.
function fakeEngine() {
    const made = [];
    class Fake {
        constructor() { made.push(this); this.started = false; }
        start() { if (this.started) throw new Error("InvalidStateError"); this.started = true; }
        stop() { this.onend && this.onend(); }
        abort() { this.aborted = true; this.onerror && this.onerror({ error: "aborted" }); this.onend && this.onend(); }
        // results: [[text, isFinal], ...] -- the whole session so far, as the API delivers it
        hear(results, resultIndex = 0) {
            const list = results.map(([t, f]) => Object.assign([{ transcript: t }], { isFinal: f }));
            this.onresult({ results: list, resultIndex });
        }
        fail(error) { this.onerror({ error }); this.onend(); }
        end() { this.onend(); }
    }
    return { Fake, made };
}

function setup() {
    const { Fake, made } = fakeEngine();
    const log = { interim: [], final: [], states: [], errors: [] };
    const l = new Listener({ Recognition: Fake, onInterim: t => log.interim.push(t), onFinal: t => log.final.push(t),
                             onState: s => log.states.push(s), onError: (c, m) => log.errors.push([c, m]) });
    return { l, made, log };
}

test("speak: interim subtitles, then one final transcript", () => {
    const { l, made, log } = setup();
    assert.equal(l.start(), true);
    const r = made[0];
    assert.equal(r.lang, "en-AU"); assert.equal(r.continuous, false); assert.equal(r.interimResults, true);
    r.hear([["my name", false]]);
    r.hear([["my name is", false]]);
    r.hear([["my name is sabin", true]]);
    r.end();
    assert.deepEqual(log.interim, ["my name", "my name is", "my name is sabin"]);
    assert.deepEqual(log.final, ["my name is sabin"]);
    assert.deepEqual(log.states, ["listening", "idle"]);
    assert.deepEqual(log.errors, []);
});

test("several final results in one session are joined once, not repeated", () => {
    const { l, made, log } = setup();
    l.start();
    made[0].hear([["thank you", true]]);
    made[0].hear([["thank you", true], ["for helping me", false]], 1);
    made[0].hear([["thank you", true], ["for helping me", true]], 1);
    made[0].end();
    assert.deepEqual(log.final, ["thank you for helping me"]);
});

test("browser ends without a final result: the last interim text is used", () => {
    const { l, made, log } = setup();
    l.start();
    made[0].hear([["hello", false]]);
    made[0].end();
    assert.deepEqual(log.final, ["hello"]);
});

test("nothing heard: a no-speech message, no transcript", () => {
    const { l, made, log } = setup();
    l.start(); made[0].end();
    assert.deepEqual(log.final, []);
    assert.equal(log.errors[0][0], "no-speech");
});

test("permission denied: a plain message, back to idle, nothing translated", () => {
    const { l, made, log } = setup();
    l.start(); made[0].fail("not-allowed");
    assert.deepEqual(log.final, []);
    assert.equal(log.errors.length, 1);
    assert.match(log.errors[0][1], /Microphone access was blocked/);
    assert.equal(l.state, "idle");
});

test("every API error code has a message; 'aborted' is silent", () => {
    for (const c of ["not-allowed", "service-not-allowed", "no-speech", "audio-capture", "network", "language-not-supported", "bad-grammar"])
        assert.ok(describeError(c).length > 20, c);
    assert.equal(describeError("aborted"), null);
});

test("pressing again while listening stops (and still delivers what was heard)", () => {
    const { l, made, log } = setup();
    l.toggle();
    made[0].hear([["welcome to australia", false]]);
    l.toggle();
    assert.deepEqual(log.final, ["welcome to australia"]);
    assert.equal(l.state, "idle");
    assert.equal(made.length, 1);
});

test("a second start while listening is ignored (one session at a time)", () => {
    const { l, made } = setup();
    assert.equal(l.start(), true);
    assert.equal(l.start(), false);
    assert.equal(made.length, 1);
});

test("cancel throws the speech away", () => {
    const { l, made, log } = setup();
    l.start(); made[0].hear([["something", false]]);
    l.cancel();
    assert.deepEqual(log.final, []); assert.deepEqual(log.errors, []);
    assert.equal(made[0].aborted, true); assert.equal(l.state, "idle");
});

test("start() failing in the engine is reported, state stays idle", () => {
    const { l, made, log } = setup();
    l.start(); made[0].end();            // finished session
    made.length = 0;
    const l2 = new Listener({ Recognition: class { start() { throw new Error("busy"); } }, onError: (c, m) => log.errors.push([c, m]) });
    assert.equal(l2.start(), false);
    assert.equal(l2.state, "idle");
    assert.equal(log.errors.at(-1)[0], "start-failed");
});

test("unsupported browser (no SpeechRecognition): says so, never throws", () => {
    assert.equal(getRecognition({}), null);
    const errors = [];
    const l = new Listener({ Recognition: null, onError: (c, m) => errors.push([c, m]) });
    assert.equal(l.supported, false);
    assert.equal(l.start(), false);
    assert.match(errors[0][1], /Chrome, Edge or Safari/);
});

test("transcript as a sentence: first letter capitalised, no punctuation invented", () => {
    assert.equal(asSentence("my name is sabin"), "My name is sabin");
    assert.equal(asSentence("  where is the toilet?  "), "Where is the toilet?");
    assert.equal(asSentence("how are you"), "How are you");
    assert.equal(asSentence(""), "");
});
