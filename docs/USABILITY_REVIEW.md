# Usability review: a first-time, non-technical user

Reviewed on 30 October 2026, before and after the changes below. The
reviewer used the app in Chrome on a desktop window (1400×900) and a phone
viewport (390×844), with a scripted speech engine standing in for the
microphone. It has not yet been tested with real users.

## Five most serious problems found

| # | Problem | Who it hurts | Fix |
|---|---|---|---|
| 1 | **Labels used internal sign names.** The figure was captioned "Currently showing WHEREABOUTS", and tiles showed WHEREABOUTS, TOILET ABC, "Needs review" and "Unavailable". "Where" was nowhere on screen. | Everyone, especially first-time users | The caption now reads **"Now showing: Where"** and the tiles show the user's own words. The internal name moved to the tooltip and the details panel. |
| 2 | **There was no overall status.** Nothing said "listening", "loading" or "done", and playback looped forever, so it never finished. | First-time users, people unsure whether it is working | A status bar above the figure shows **Ready, Listening…, Preparing signs…, Playing signs…, Finished**, with a **Replay** button at the end. Looping is off by default (still in Advanced settings). |
| 3 | **What was heard and what is signed were in different places.** The transcript was in the input card, and the signing was in the viewer. | Deaf users reading along; anyone checking for mishearing | **"You said: …"** sits directly under the figure, with the current word underlined. The input card says **"Wrong word? Fix it in the box below and press Enter."** |
| 4 | **Secondary actions competed with the main one.** Upload PDF was as large as Translate. A 4-line text box, the PDF button and three examples all came before the figure on a phone. | Phone users | The microphone is a single large round button with **"Tap to speak"**. Typing is labelled **"Or type instead"**, is 2 lines tall, and its button says **"Show signs"**. The PDF option is a small link. Examples are hidden on phones. |
| 5 | **Speed and uncertainty were unclear.** The speed menu showed only "1×", and an uncertain sign showed only an ⚠ icon. | People trying to read fingerspelling | Speed is labelled, with **"Slow (0.5×)"** and **"Normal"**. Uncertain signs are captioned **"⚠ This sign needs verification."** |

The audit also checked the following, which did not need changes:
- **Navigation:** two header links, and Advanced settings collapsed.
- **Errors:** they are already in plain words.
- **Performance:** signs load on demand and paused playback costs nothing.

## What changed (and what did not)

- **Page:** the redesign is in `frontend/index.html`. Small speech-wording changes are in `speech.js`, and nothing changed in the planner or library.
- **Figure (`renderer.js`):** the finger lines are drawn about 25% thicker and the palm tint is stronger, so hands are easier to follow on a phone. Every joint position is still exactly what the tracker measured. No motion was added, smoothed or changed.
- **Kept, just moved:** PDF upload, the editable sign plan, the source video, the gloss line and the tracking details. They are now secondary.

## The five scenarios

| Scenario | Expected | Verified by | Remaining limits |
|---|---|---|---|
| 1. First-time user speaks one sentence | Tap the big button, see "Listening…", then the words, then signs with no extra click | `test_voice.py`: phases ready, listening, playing; transcript; auto-play | Real microphone untested on this machine; Chrome and Edge need internet for speech |
| 2. Deaf user reads the transcript and watches | Everything heard is shown as text next to the figure. Nothing needs sound. | "You said" plus live text (`test_voice.py`, `test_ui.py`) | The app shows English text and signs. It does not translate Auslan into English. |
| 3. Unsupported word | It is spelled out, marked ABC, and the caption says "no sign for this word" | "my name is sabin": SABIN spelled, tiles marked | Spoken names arrive in lower case, so they are labelled "no sign" rather than "a name". The result is the same: they are spelled out. |
| 4. Slow down and replay | Replay at the end; "Slow (0.5×)" | Finished → Replay; 0.5× measured at half speed (`test_voice.py`) | n/a |
| 5. Microphone permission denied | A plain message on how to allow it; typing still works | `test_voice.py` (denied, and no-speech-support browser) | Browser permission prompts differ between browsers |

## Accessibility, measured

`tests/browser/test_ui.py` checks these in Chrome:
- **Names:** every button, field, slider and menu has an accessible name. This is read from Chrome's accessibility tree, and none are missing.
- **Keyboard:** the microphone is the first control after the skip link and header links. `M` speaks and `Esc` cancels.
- **Focus:** focus is visible, with an outline of at least 2 px.
- **Contrast:** text contrast is at least 4.5:1 on the 14 texts a first-time user reads. The lowest is 4.55.
- **Announcements:** spoken words are also shown as text, and the current sign is announced to screen readers.

## Not done

- **Real users:** no testing with real users, especially Deaf users and people with low digital literacy.
- **Figure:** the figure is still a 2D stick figure drawn from tracked points. Palm orientation and depth are not in the data. Hands are only as good as the tracking.
- **Spoken questions:** these arrive without "?", so the question word-order rule does not apply to speech.
