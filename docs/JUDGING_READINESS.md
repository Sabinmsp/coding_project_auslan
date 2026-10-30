# SignBridge: judging readiness

CDU IT Code Fair 2026. Status on 30 October 2026, the submission day.

**What it is:** you speak, type or upload English, and recorded Auslan
signs play in sequence on a 2D figure. Words with no recorded sign are
fingerspelled and labelled.

**What it is not:** a translator into grammatical Auslan, or a replacement
for an interpreter. No fluent Auslan signer has checked the output.

## Evidence by criterion

| Criterion | What judges can check themselves | Status |
|---|---|---|
| **Innovation** | Speak a sentence and the figure signs it, with no typing. Every word shows how it was handled: sign, fingerspelled, needs review or omitted. | Implemented |
| **Functionality** | Speech, transcript, plan, signs, then replay and speed, in one flow (Demo A–D in [DEMO_SCRIPT.md](DEMO_SCRIPT.md)). | Implemented and tested with a scripted speech engine; real-microphone test still to do (below) |
| **Usability** | One large **Speak** button first, a text box as the alternative, the figure as the largest element, live subtitles, keyboard shortcuts, phone layout. | Implemented |
| **Scalability** | Separate modules, signs loaded only when needed, a static site with no application server. | Implemented; not load-tested |
| **Reliability** | 9 browser test suites: errors, rapid input, a 4× slowed CPU, missing files, denied microphone, unsupported browser. | Implemented |
| **Social impact** | Lowers the effort for a hearing person to show something in Auslan: speak instead of looking up signs one by one. | Prototype: needs Deaf community input before any real use |

## What is different from a sign dictionary

A dictionary such as Auslan Signbank looks up **one word** and plays **one
video**. SignBridge takes a **whole sentence**, whether spoken, typed or
from a PDF. It:

- chooses a recorded sign for each word, or fingerspells it;
- shows the reason for each choice;
- plays the signs as one continuous motion on a single figure, rather than separate video clips.

The signs are stored as motion data (about 45 KB compressed per sign), so a
sentence loads faster than the equivalent videos.

**Not new:** speech-to-text, text-to-sign avatars and fingerspelling
fallbacks all exist elsewhere, for other sign languages and in research.
The contribution here is putting them together for Auslan, built from
openly available recordings, with every decision visible and no invented
motion.

## Voice input: how it works

```
Speak ─► browser speech recognition (Web Speech API, en-AU)
         │  interim words ─► live subtitle under the button
         ▼  final transcript
      text box ─► the same planner as typed text ─► signs play
```

- **Code:** `frontend/src/speech.js`. It only turns speech into text and knows nothing about signs.
- **One sentence per press.** The microphone turns itself off after a pause. Pressing again stops early, and `Esc` cancels.
- **Errors in plain words.** A blocked microphone, no microphone, nothing heard, no internet or an unsupported browser (Firefox) each get a message. Typing keeps working in every case.
- **Privacy.** SignBridge does not record, keep or upload audio. The browser's speech service does the recognition, and Chrome and Edge send the audio to their vendor's servers to do it. The page says this next to the button and in About.
- **Corrections.** The transcript lands in the text box, so a misheard word can be fixed and replayed.

## Tests (run on 30 Oct 2026)

| Suite | Result |
|---|---|
| Node unit tests, including 12 new voice tests (fake speech engine) | 100 / 100 pass |
| Library integrity check | pass |
| Python pipeline, AI-summary and LLM-validation tests | 34 / 34 pass |
| Browser suites (headless Chrome), including the new voice suite (25 checks) | 9 / 9 pass on the full library. The stress suite failed once inside a full run (clock check), then passed 3 times alone; cause not found. |
| Same suites against the deploy build (`dist/`, 90.2 MB) | 7 pass. Robustness fails only because its test picks an unreliable sign that the partial build does not ship. |

The browser voice suite replaces the microphone with a scripted engine
that behaves like the Web Speech API. It covers speaking, live subtitles,
the transcript, automatic playback, fingerspelled words, replay at 0.5×,
the `M` and `Esc` keys, early stop, a denied microphone, an unsupported
browser, and the phone layout.

**Not yet tested:** a real microphone in a real browser (no microphone on
the test machine), Safari, real phones, and a noisy room. Do this before
the 5 November demo.

## Scalability, realistically

- **At start the page loads:** the sign list (0.5 MB, 118 KB compressed) and the keyword list (270 KB, 67 KB compressed).
- **Per sign:** about 140 KB of motion data (about 45 KB compressed), fetched the first time the sign is needed. The browser keeps the 80 most recent in memory, and the CDN caches the files for a day.
- **No application server.** More users means more CDN downloads, not more servers. Speech recognition runs in each user's browser.
- **The optional AI summary** for PDFs is the only server code. It falls back to the offline summary if it is unavailable.
- **Capacity:** not load-tested, so no user count is claimed. The full library is about 660 MB of motion data. The demo build carries only the signs its demo text needs (86 MB), because of Vercel's upload limit.
- **More vocabulary:** add recordings and re-run the pipeline; no app code changes. The 89 Signbank signs were added this way.

## Ethics and licensing

- Auslan is a language of its own, with its own grammar. The page says this, and it says SignBridge does not replace interpreters.
- Every fingerspelled, uncertain or omitted word is labelled. Unreliable recordings never play without a warning.
- **Licensing, still open:**
  - **Signbank (89 signs, some letters):** CC BY-NC-ND 4.0. Attribution and non-commercial use are covered. Whether turning the videos into motion data counts as a "derivative" under the No-Derivatives term should be asked of the Signbank team.
  - **Main dictionary corpus:** its licence still needs to be confirmed.

## Implemented vs planned

| Implemented now | Planned / not done |
|---|---|
| Voice input (Chrome, Edge, Safari), live subtitles, auto-play | On-device speech for offline voice; Firefox has no Web Speech API |
| Typed and PDF input; editable plan; replay, speed, step, full screen | Review of the signing by fluent Auslan signers |
| 3,304 signs plus A–Z fingerspelling, loaded on demand | More vocabulary (most-missed words: HOW, PLEASE, FOR, TOILET, MORNING) |
| Static deploy build with Vercel/Netlify config | The deployed site itself (needs your Vercel login) |
| 9 browser test suites | Real-microphone, real-phone, noisy-room and load tests |
| Simple ordering rules (time first; wh-word last when "?") | Auslan grammar: use of space, facial grammar, classifiers |
