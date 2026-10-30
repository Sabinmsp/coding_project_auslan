"""
Browser test: the Code Fair layout and controls, plus the end-to-end
checklist (single sign, two signs, 5+ words, unknown word, fingerspelled
name, rapid switching, pause/resume, speed, scrub, mobile viewport).

    python3 tests/browser/test_controls.py [port]      # default 8003

Needs the app served on that port and Google Chrome. Exit code 1 on failure.
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdp import launch  # noqa: E402

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8003
proc, c = launch(9781 + PORT % 10, f"p-controls{PORT}")
for d in ("Page", "Runtime", "Network"):
    c.call(f"{d}.enable")
c.call("Network.setCacheDisabled", cacheDisabled=True)
c.call("Page.addScriptToEvaluateOnNewDocument", source="""
  window.__errs = [];
  addEventListener('error', e => __errs.push('error: ' + e.message));
  addEventListener('unhandledrejection', e => __errs.push('rejection: ' + (e.reason && e.reason.message || e.reason)));
  const ce = console.error; console.error = (...a) => { __errs.push('console: ' + a.join(' ')); ce(...a); };""")
J = c.js
ok_all = True


def check(name, cond, detail=""):
    global ok_all
    ok_all &= bool(cond)
    print(("PASS " if cond else "FAIL ") + name + (f"   [{detail}]" if detail != "" else ""))


def wait_playing(timeout=10):
    for _ in range(int(timeout / 0.1)):
        if J("!!(auslan.timeline && auslan.playing)"):
            return True
        time.sleep(0.1)
    return False


def load(blocked=(), query=""):
    c.call("Network.setBlockedURLs", urls=list(blocked))
    c.call("Page.navigate", url=f"http://localhost:{PORT}/{query}")
    for _ in range(80):
        time.sleep(0.25)
        if J("document.readyState === 'complete' && !!window.auslan") and (blocked or J("!!auslan.lib")):
            return


def key(k, code=None):
    for t in ("keyDown", "keyUp"):
        c.call("Input.dispatchKeyEvent", type=t, key=k, code=code or k)


shape = lambda: J("auslan.plan.steps.map(s=>s.kind==='sign'?s.id:s.kind==='spell'?'fs:'+s.letters.join(''):'-'+s.en).join(' ')")
step_at = lambda: J("auslan.timeline.clips[auslan.timeline.items.find(i=>i.type==='clip'&&auslan.t>=i.t0&&auslan.t<i.t1)?.clip ?? 0].step")

# ---- startup error: the library is missing ---------------------------------
load(blocked=["*manifest.json"])
time.sleep(1.0)
msg = J("document.getElementById('status').textContent")
check("missing library: a helpful message, not a blank page",
      not J("document.getElementById('status').hidden") and "serve.py" in msg, msg[:70])
load()
check("ready: the stage invites input", "type a sentence" in J("document.getElementById('status').textContent").lower())

# ---- E2E 1: single sign -------------------------------------------------------
J("auslan.say('hello')"); wait_playing(); time.sleep(0.4)
check("E2E single sign", shape() == "hello" and J("document.getElementById('status').hidden")
      and J("document.querySelectorAll('#steps button').length") == 1, shape())
check("  sign panel describes it", "HELLO" in J("document.getElementById('info-body').textContent"))

# ---- E2E 2: two signs + step strip + prev/next -------------------------------
J("auslan.say('thank you doctor')"); wait_playing(); time.sleep(0.2)
check("E2E two-sign sequence", shape() == "thank-you doctor", shape())
J("document.querySelectorAll('#steps button')[1].click()"); time.sleep(0.3)
check("step strip: clicking a step jumps to it, still playing", step_at() == 1 and J("auslan.playing"), step_at())
time.sleep(0.4)                                          # well inside the sign (> 0.4 s)
J("document.getElementById('play').click()")              # pause
J("document.getElementById('prev').click()"); time.sleep(0.2)
check("prev button: back to the start of the current sign, stays paused",
      not J("auslan.playing") and step_at() == 1, f"t={J('auslan.t'):.2f}")
J("document.getElementById('prev').click()"); time.sleep(0.2)
check("prev again: previous sign", step_at() == 0 and J("auslan.t") == 0)
J("document.body.focus()"); key("ArrowRight"); time.sleep(0.2)
check("→ key: next sign", step_at() == 1, step_at())
key("ArrowLeft"); key("ArrowLeft"); time.sleep(0.2)
check("← key: previous sign", step_at() == 0)
key(" ", "Space"); time.sleep(0.3)
check("Space key: plays", J("auslan.playing"))
J("document.getElementById('sentence-input').focus()"); key("ArrowLeft"); time.sleep(0.1)
check("arrow keys in the text box stay in the text box", J("auslan.playing"))

# ---- E2E 3: 5+ words ------------------------------------------------------------
J("auslan.say('Please pay your bill tomorrow.')"); wait_playing()
check("E2E 5+ word sentence", shape() == "tomorrow fs:PLEASE pay your bill"
      and J("document.querySelectorAll('#steps button').length") == 5, shape())

# ---- E2E 4/5: unknown word, fingerspelled name, compact fingerspelling --------
J("auslan.say('zxqv')"); wait_playing(); time.sleep(0.3)
check("E2E unknown word: fingerspelled, says no sign exists",
      "no sign for this word" in J("document.getElementById('sub').textContent"), J("document.getElementById('sub').textContent")[:70])
J("auslan.say('My name is Sabin.')"); wait_playing(); time.sleep(0.2)
compact = J("auslan.timeline.duration")
check("E2E fingerspelled name: labelled as a name",
      J("auslan.plan.steps.find(s=>s.en==='Sabin').reason") == "name")
J("document.getElementById('compact').click()"); wait_playing(); time.sleep(0.3)
full = J("auslan.timeline.duration")
check("compact fingerspelling switch: whole letter recordings are much longer",
      full > compact * 1.5, f"compact {compact:.1f}s, full {full:.1f}s")
J("document.getElementById('compact').click()"); wait_playing()

# ---- alternatives panel edits the plan ------------------------------------------
J("auslan.say('I need help.')"); wait_playing(); time.sleep(0.2)
J("document.querySelectorAll('#steps button')[0].click()"); time.sleep(0.3)
alt = J("[...document.querySelectorAll('#alts button')].find(b=>b.textContent.startsWith('fingerspell') && !b.disabled)?.textContent")
J("[...document.querySelectorAll('#alts button')].find(b=>b.textContent.startsWith('fingerspell') && !b.disabled).click()")
wait_playing(); time.sleep(0.2)
check("alternatives: choosing one replays the edited plan, marked as chosen",
      shape().startswith("fs:I") and J("document.querySelector('#plan .chip.reviewed') !== null"), f"{alt} -> {shape()}")

# ---- nothing to sign ---------------------------------------------------------------
J("auslan.say('the')"); time.sleep(0.8)
check("all words omitted: says so on the stage",
      "Nothing to sign" in J("document.getElementById('status').textContent")
      and not J("document.getElementById('status').hidden"))
J("document.getElementById('sentence-input').value='   '; document.getElementById('sentence-go').click()")
time.sleep(0.3)
check("blank input: ignored, no error", not J("window.__errs"))

# ---- E2E 6: rapid switching via the example buttons --------------------------------
J("[...document.querySelectorAll('#examples button')].forEach(b => b.click())"); wait_playing(); time.sleep(0.6)
check("E2E rapid switching: the last example wins",
      J("auslan.plan.text") == J("[...document.querySelectorAll('#examples button')].at(-1).textContent")
      and J("auslan.timeline.plan === auslan.plan"), J("auslan.plan.text"))

# ---- E2E 7/8/9: pause/resume, speed 1.5, scrub ------------------------------------------
J("document.getElementById('play').click()"); time.sleep(0.2); tp = J("auslan.t"); time.sleep(0.4)
held = abs(J("auslan.t") - tp) < 1e-9
J("document.getElementById('play').click()"); time.sleep(0.5)
check("E2E pause/resume", held and J("auslan.playing") and J("auslan.t") > tp + 0.2)
J("document.getElementById('speed').value='1.5'; document.getElementById('speed').dispatchEvent(new Event('change'))")
t0 = J("auslan.t"); time.sleep(1.0); dt = J("auslan.t") - t0
check("E2E speed 1.5x", 1.2 < dt < 1.8 or dt < 0, f"{dt:.2f}s per second")
J("document.getElementById('speed').value='1'; document.getElementById('speed').dispatchEvent(new Event('change'))")
J("const s=document.getElementById('scrub'); s.value=String(Math.round(auslan.timeline.duration*500)); s.dispatchEvent(new Event('input'))")
time.sleep(0.3)
check("E2E scrub: pauses at the slider position",
      not J("auslan.playing") and abs(J("auslan.t") - J("auslan.timeline.duration") / 2) < 0.01)

# ---- spike switch rebuilds the library without errors --------------------------------------
J("document.getElementById('despike').click()"); wait_playing(); time.sleep(0.3)
check("raw-tracking switch: replays with a fresh library", J("auslan.playing") and not J("window.__errs"))
J("document.getElementById('despike').click()"); wait_playing()

# ---- E2E 10: mobile viewport -----------------------------------------------------------------
c.call("Emulation.setDeviceMetricsOverride", width=390, height=844, deviceScaleFactor=2, mobile=True)
time.sleep(0.6)
over = J("document.documentElement.scrollWidth > document.documentElement.clientWidth")
canvas_h = J("document.getElementById('canvas').getBoundingClientRect().height")
ctrl = J("(()=>{const r=document.getElementById('play').getBoundingClientRect();return r.width>=40&&r.height>=32})()")
check("E2E mobile viewport: no sideways scroll, avatar visible, controls tappable",
      not over and canvas_h > 250 and ctrl, f"canvas {canvas_h:.0f}px")
c.call("Emulation.clearDeviceMetricsOverride")

check("no page errors", not J("window.__errs"), J("window.__errs"))
print("ALL PASS" if ok_all else "SOME FAILED")
proc.kill()
sys.exit(0 if ok_all else 1)
