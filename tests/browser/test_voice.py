"""
Browser test: voice input end to end, in real Chrome, with a scripted
speech engine in place of the microphone (headless Chrome has no
microphone, and the real recognition service is not reachable from tests).

    python3 tests/browser/test_voice.py [port]      # default 8003

What the fake does is what the Web Speech API does: interim results word
by word, then one final result, then `end` -- or an error. Everything after
that (subtitles, transcript, planner, avatar) is the real page.
"""
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from cdp import launch  # noqa: E402

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8003
ok_all = True

FAKE = r"""
(() => {
  window.__errs = [];
  addEventListener('error', e => __errs.push('error: ' + e.message));
  addEventListener('unhandledrejection', e => __errs.push('rejection: ' + (e.reason && e.reason.message || e.reason)));
  const mode = new URLSearchParams(location.search).get('voice');
  if (mode === 'none') { window.SpeechRecognition = undefined; window.webkitSpeechRecognition = undefined; return; }
  window.__said = 'my name is sabin';
  window.__started = 0;
  class Fake {
    start() {
      __started++; window.__lang = this.lang; this.live = true;
      setTimeout(() => {
        if (mode === 'deny') { this.onerror({ error: 'not-allowed' }); this.onend(); return; }
        const words = __said.split(' ');
        let i = 0;
        const step = () => {
          if (!this.live) return;
          i++;
          const r = [{ transcript: words.slice(0, i).join(' ') }];
          r.isFinal = i === words.length;
          this.onresult({ resultIndex: 0, results: [r] });
          if (r.isFinal) setTimeout(() => { this.live = false; this.onend(); }, 60);
          else setTimeout(step, 150);
        };
        step();
      }, 200);
    }
    stop() { if (this.live) { this.live = false; setTimeout(() => this.onend(), 10); } }
    abort() { if (this.live) { this.live = false; this.onerror({ error: 'aborted' }); this.onend(); } }
  }
  window.SpeechRecognition = Fake; window.webkitSpeechRecognition = Fake;
})();
"""


def check(name, cond, detail=""):
    global ok_all
    ok_all &= bool(cond)
    print(("PASS " if cond else "FAIL ") + name + (f"   [{detail}]" if detail != "" else ""))


def open_page(c, mode):
    c.call("Page.navigate", url=f"http://localhost:{PORT}/?voice={mode}")
    for _ in range(80):
        time.sleep(0.25)
        if c.js("!!(window.auslan && auslan.lib)"):
            return


def wait(c, expr, timeout=8):
    for _ in range(int(timeout * 20)):
        if c.js(expr):
            return True
        time.sleep(0.05)
    return False


proc, c = launch(9751 + PORT % 10, f"p-voice{PORT}")
for d in ("Page", "Runtime"):
    c.call(f"{d}.enable")
c.call("Page.addScriptToEvaluateOnNewDocument", source=FAKE)
J = c.js
live = "document.getElementById('live')"

# ---- A: speak -> transcript -> signs ---------------------------------------
open_page(c, "ok")
check("microphone button is the first control, enabled, with a label",
      J("!document.getElementById('mic').disabled") and J("document.getElementById('mic-label').textContent") == "Speak")
check("privacy note next to the microphone", "does not record or keep audio" in J("document.getElementById('mic-note').textContent"))
J("document.getElementById('mic').click()")
check("press Speak: listening state shown (button pressed, label changes)",
      wait(c, "document.getElementById('mic').getAttribute('aria-pressed') === 'true'", 1)
      and "Listening" in J("document.getElementById('mic-label').textContent"))
check("  recognition language is Australian English", J("window.__lang") == "en-AU", J("window.__lang"))
check("  live subtitle shows the words while speaking",
      wait(c, f"{live}.className === 'interim' && {live}.textContent.startsWith('my name')", 3), J(f"{live}.textContent"))
check("final transcript fills the text box",
      wait(c, "document.getElementById('sentence-input').value === 'My name is sabin'", 5),
      J("document.getElementById('sentence-input').value"))
check("  and is shown as what was heard", J(f"{live}.textContent").startswith("Heard:"), J(f"{live}.textContent"))
check("  the signs play automatically",
      wait(c, "!!(auslan.playing && auslan.plan && auslan.plan.text === 'My name is sabin' && auslan.timeline)", 8))
steps = J("auslan.plan.steps.map(s => s.kind === 'sign' ? s.gloss : s.kind === 'spell' ? 'fs:' + s.letters.join('') : '-').join(' ')")
check("  available sign played, unknown words fingerspelled and marked", steps.startswith("MY") and "fs:SABIN" in steps
      and J("document.querySelectorAll('#steps .spell').length") >= 1, steps)
check("  microphone off again afterwards", J("document.getElementById('mic').getAttribute('aria-pressed')") == "false"
      and not J("auslan.listening"))

# replay and speed still work on a spoken sentence
J("document.getElementById('replay').click()"); time.sleep(0.1)
t0 = J("auslan.t")
J("(s => { s.value = '0.5'; s.dispatchEvent(new Event('change')); })(document.getElementById('speed'))")
a = J("auslan.t"); time.sleep(1.0); b = J("auslan.t")
check("replay restarts; 0.5x speed plays at half speed", t0 < 0.3 and 0.35 < b - a < 0.65, f"t0={t0:.2f} advanced {b - a:.2f}s in 1s")
J("(s => { s.value = '1'; s.dispatchEvent(new Event('change')); })(document.getElementById('speed'))")

# typing still works
J("auslan.say('Thank you for helping me.')")
check("typed text still translates and plays", wait(c, "auslan.plan.text === 'Thank you for helping me.' && auslan.playing", 6))

# keyboard: M starts, Esc cancels without translating
J("document.activeElement && document.activeElement.blur()")
J("window.__said = 'please call me tomorrow morning at the hospital'")
J("document.body.dispatchEvent(new KeyboardEvent('keydown', { key: 'm', bubbles: true }))")
check("M key starts listening", wait(c, "auslan.listening", 1))
time.sleep(0.4)
J("document.body.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }))")
time.sleep(1.2)
check("Esc stops listening and nothing is translated", not J("auslan.listening")
      and J("auslan.plan.text") == "Thank you for helping me.", J("auslan.plan.text"))

# a second press while listening stops early and translates what was heard
J("window.__said = 'welcome to australia'")
J("document.getElementById('mic').click()")
wait(c, f"{live}.textContent.startsWith('welcome')", 2)
J("document.getElementById('mic').click()")
check("pressing again stops early and signs what was heard",
      wait(c, "auslan.plan && auslan.plan.text.startsWith('Welcome') && auslan.playing", 6), J("auslan.plan.text"))
check("only one recognition session per press", J("window.__started") == 3, J("window.__started"))
check("no page errors", not J("window.__errs"), J("window.__errs"))

# ---- B: permission denied ------------------------------------------------------
open_page(c, "deny")
J("document.getElementById('mic').click()")
check("microphone blocked: a plain message",
      wait(c, f"{live}.className === 'error' && {live}.textContent.includes('Microphone access was blocked')", 3),
      J(f"{live}.textContent"))
check("  nothing is translated, button back to Speak", not J("auslan.plan") and
      J("document.getElementById('mic').getAttribute('aria-pressed')") == "false")
J("auslan.say('I love Australia.')")
check("  typing still works after a denied microphone", wait(c, "auslan.playing && auslan.plan.text === 'I love Australia.'", 6))

# ---- C: browser without speech recognition (Firefox) ---------------------------
open_page(c, "none")
check("no speech API: button disabled with the reason", J("document.getElementById('mic').disabled")
      and "isn't available in this browser" in J(f"{live}.textContent"), J(f"{live}.textContent"))
J("auslan.say('Welcome to Australia.')")
check("  typing still works", wait(c, "auslan.playing && auslan.plan.text === 'Welcome to Australia.'", 6))
check("no page errors", not J("window.__errs"), J("window.__errs"))
proc.kill()

# ---- D: phone: the microphone is on the first screen --------------------------
proc, c = launch(9752 + PORT % 10, f"p-voicephone{PORT}", size="390,844")
for d in ("Page", "Runtime"):
    c.call(f"{d}.enable")
c.call("Page.addScriptToEvaluateOnNewDocument", source=FAKE)
open_page(c, "ok")
r = c.js("(b => [b.top, b.bottom, b.width])(document.getElementById('mic').getBoundingClientRect())")
check("phone: Speak button visible without scrolling, full width, 56px tall", r[1] < c.js("innerHeight") and r[2] > 250,
      f"top {r[0]:.0f} bottom {r[1]:.0f} width {r[2]:.0f}")
check("phone: no horizontal scrolling", c.js("document.documentElement.scrollWidth <= innerWidth + 1"))
proc.kill()

print("ALL PASS" if ok_all else "SOME FAILED")
sys.exit(0 if ok_all else 1)
