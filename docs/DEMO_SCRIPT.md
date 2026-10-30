# Judging demo: 5 November 2026

Five short demos, about 6 minutes in all. Each one uses sentences whose
result is known in advance (checked against the current sign library), so
the demo is repeatable.

## Before the judges arrive (10 minutes)

| Check | How |
|---|---|
| Browser | **Chrome or Edge** on the laptop. Safari also has voice input; Firefox does not. |
| Address | The deployed `https://` link, or `http://localhost:8003`. Voice input only works on `https://` or `localhost`. |
| Microphone | Press **Speak** once and allow the microphone. Say "hello" to confirm that it is heard. |
| Internet | Chrome's and Edge's speech recognition uses their online speech service. Without internet, use typing (Demo B). |
| Warm-up | Play every demo sentence once. Their sign files are then cached and later plays start at once. |
| Noise | In a noisy hall, hold the laptop microphone close or use a headset. If speech is misheard, say so and type the sentence instead. |
| Backup | A local copy: `python3 backend/serve.py 8003` and open `http://localhost:8003`. |

## Demo A: speak and watch (90 s)

1. Press **Speak** (or press `M`).
2. Say: **"I need to see a doctor."**
3. Point out three things:
   - The words appear live under the button while you speak.
   - The full sentence lands in the text box ("Heard: …").
   - The figure signs **I, NEED, SEE, DOCTOR** without another click.
4. Say: "*to* and *a* are omitted by the planner. Auslan does not sign every English word, but this is a simple rule, not Auslan grammar."

Other sentences that sign fully: "Nice to meet you", "I am deaf", "See you tomorrow".

## Demo B: type (45 s)

1. Click the text box and type **"Welcome to Australia."**
2. Press **Enter**. The figure signs **WELCOME, AUSTRALIA**.
3. Open **Translation details** to show that each word's handling is explained and can be changed from a menu.

## Demo C: words without a sign (60 s)

1. Speak or type **"My name is Sabin."**
   - **MY** is a recorded sign.
   - **NAME** is fingerspelled. The recordings have no reliable sign for it, and the tile is marked **ABC**.
   - **SABIN** is fingerspelled because it is a name.
2. Type **"Where is the toilet?"**
   - **TOILET** is fingerspelled (no recording).
   - **WHERE** plays the sign WHEREABOUTS, marked **⚠ Needs review**. It is the planner's best guess and is shown as one.
3. Say: "SignBridge never invents motion. A word with no recorded sign is spelled letter by letter and labelled that way."

## Demo D: replay and speed (30 s)

1. With any sentence loaded, press **Restart** (↻).
2. Set the speed to **0.5×**. This helps with reading fingerspelling.
3. Use **⏮ ⏭** (or ← →) to step sign by sign. Click a tile in **Sign sequence** to jump to that sign.
4. Press **F** for full screen.

## Demo E: architecture (90 s)

Show `docs/images/system_design.png` or say:

```
 🎤 voice ─► speech.js ─┐
 ⌨ typed  ──────────────┼─► planner.js ─► library.js ─► timeline.js ─► player.js ─► renderer.js
 📄 PDF ─► document.js ─┘   words→signs    loads only     joins clips    one clock     draws the
                            (rules,        the signs      into one                     figure
                             explained)    needed         motion
```

- **Separate parts.** Speech recognition only produces text. Every input goes through the same planner, so voice, typing and PDF can never disagree.
- **Static site.** It is hosted as static files with no application server, so more users do not mean more servers. Voice recognition runs in each visitor's browser.
- **Loaded on demand.** At start the page fetches a 0.5 MB sign list (118 KB compressed). Each sign is about 140 KB of motion data (about 45 KB compressed), fetched the first time it is needed and then cached.
- **Growing the vocabulary** means adding recordings and re-running the pipeline. 89 Signbank signs were added this way without changing any app code.

## If something goes wrong

| Problem | What to say or do |
|---|---|
| "Microphone access was blocked" | Click the camera/microphone icon in the address bar → Allow, then press Speak again. Or type. |
| "No speech was heard" | Press Speak again and speak right after pressing. |
| Misheard words | The transcript is in the text box: correct it and press Enter. This is a real feature. |
| No internet | Typing, PDF and playback all work offline once loaded. Only voice needs the browser's speech service. |
| Figure doesn't move | Press Restart. If still stuck, reload the page; the files come back from the cache. |

## What not to claim

- It is **not** an Auslan translator and does not replace an interpreter.
- The signing has **not** been checked by fluent Auslan signers.
- Word order uses two simple rules: time words first, and the question word last when the sentence ends with "?".
  Speech arrives without punctuation, so spoken questions keep English order.
