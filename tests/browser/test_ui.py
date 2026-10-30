"""
Browser test: the simplified main screen, the Advanced drawer, dialogs and
keyboard use.   python3 tests/browser/test_ui.py [port]   (default 8003)
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdp import launch  # noqa: E402

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8003
proc, c = launch(9731 + PORT % 10, f"p-ui{PORT}")
for d in ("Page", "Runtime"):
    c.call(f"{d}.enable")
c.call("Page.addScriptToEvaluateOnNewDocument", source="""
  window.__errs = [];
  addEventListener('error', e => __errs.push('error: ' + e.message));
  addEventListener('unhandledrejection', e => __errs.push('rejection: ' + (e.reason && e.reason.message || e.reason)));""")
c.call("Page.navigate", url=f"http://localhost:{PORT}/")
for _ in range(80):
    time.sleep(0.25)
    if c.js("!!(window.auslan && auslan.lib)"):
        break
J = c.js
ok_all = True


def check(name, cond, detail=""):
    global ok_all
    ok_all &= bool(cond)
    print(("PASS " if cond else "FAIL ") + name + (f"   [{detail}]" if detail != "" else ""))


VK = {"Enter": 13, "Escape": 27, "Tab": 9}


def key(k, code=None, text=None, mods=0):
    kw = dict(key=k, code=code or k, modifiers=mods, windowsVirtualKeyCode=VK.get(k, ord(k.upper()) if len(k) == 1 else 0))
    c.call("Input.dispatchKeyEvent", type="keyDown", **kw, **({"text": text} if text else {}))
    c.call("Input.dispatchKeyEvent", type="keyUp", **kw)


visible = lambda sel: J(f"(()=>{{const e=document.querySelector({sel!r});return !!e && e.getClientRects().length>0}})()")

check("first screen: input, Translate & Play, avatar, controls visible",
      all(visible(s) for s in ("#sentence-input", "#sentence-go", "#canvas", "#play")))
check("first screen: developer panels hidden (gloss editor, source video, alternatives, tracking, document)",
      not any(visible(s) for s in ("#glossline", "#reference", "#alts", "#tracking", "#docpanel")))
check("two columns on a wide screen: input on the left, avatar on the right",
      J("(()=>{const a=document.getElementById('sentence-input').getBoundingClientRect(), b=document.getElementById('canvas').getBoundingClientRect(); return a.right <= b.left + 1})()"))
check("limitations notice visible on the first screen", visible(".notice") and "not checked by a fluent auslan signer"
      in J("document.querySelector('.notice').textContent").lower())

# keyboard: type, Enter plays; Shift+Enter is a new line
J("const i=document.getElementById('sentence-input'); i.value=''; i.focus()")
for ch in "I love Australia":
    key(ch, "Space" if ch == " " else f"Key{ch.upper()}", ch)
key("Enter", "Enter", "\r", mods=8)                       # Shift+Enter
check("Shift+Enter adds a line instead of playing", "\n" in J("document.getElementById('sentence-input').value"))
J("document.getElementById('sentence-input').value='I love Australia'")
key("Enter", "Enter", "\r")
for _ in range(60):
    time.sleep(0.1)
    if J("!!(auslan.timeline && auslan.playing && auslan.plan.text==='I love Australia')"):
        break
tiles = J("[...document.querySelectorAll('#steps button')].map(b=>b.textContent)")
check("Enter plays; one tile per sign with its marker", tiles == ["I✓", "LOVE✓", "AUSTRALIA✓"], tiles)
J("auslan.say('My name is Sabin.')"); time.sleep(1.5)
tiles = J("[...document.querySelectorAll('#steps button')].map(b=>b.textContent)")
check("fingerspelled words are marked ABC", tiles == ["MY✓", "NAMEABC", "SABINABC"], tiles)

# Tab order reaches the main actions
J("document.getElementById('sentence-input').focus()")
order = []
for _ in range(8):
    key("Tab", "Tab")
    order.append(J("document.activeElement.id || document.activeElement.textContent.trim().slice(0,20)"))
check("Tab from the text box reaches Translate & Play", "sentence-go" in order, order)

# Advanced drawer
J("document.getElementById('adv-toggle').click()"); time.sleep(0.2)
check("Advanced settings opens the gloss line, video, alternatives",
      all(visible(s) for s in ("#glossline", "#reference", "#alts")) and
      J("document.getElementById('adv-toggle').getAttribute('aria-expanded')") == "true")
overlap = max(J(f"""(() => {{ scrollTo(0, {y}); const s = document.getElementById('stagecol').getBoundingClientRect(),
    a = document.getElementById('advanced').getBoundingClientRect(); return s.bottom - a.top; }})()""") for y in range(0, 3000, 150))
check("  the pinned avatar never covers the Advanced panel while scrolling", overlap <= 0, f"{overlap:.0f}px")
check("  the panel opens directly under its button",
      0 <= J("document.getElementById('advanced').getBoundingClientRect().top - document.getElementById('adv-toggle').getBoundingClientRect().bottom") < 40)
J("scrollTo(0, 0)")
J("document.getElementById('adv-toggle').click()"); time.sleep(0.2)
check("and closes again", not visible("#glossline"))

# left panel: plan + vocabulary lists
J("auslan.say('Where is the hospital? My name is Sabin. I love Australia')"); time.sleep(1.2)
check("sign sequence shown on the left after translating", visible("#seqpanel") and visible("#steps button"))
check("translation details collapsed by default", visible("#details") and not J("document.getElementById('details').open"))
J("document.getElementById('details').open = true"); time.sleep(0.2)
check("translation details: a chip per step", J("document.querySelectorAll('#plan .chip').length") >= 8 and visible("#plan"))
vocab = J("document.getElementById('vocab').innerText")
check("vocabulary lists: signs, no-sign words, names, left-out words",
      all(k in vocab for k in ("Available recorded signs", "no recorded sign", "Names, fingerspelled", "Left out by the current planner"))
      and "Sabin" in vocab and "hospital" in vocab.lower(), vocab[:90].replace("\n", " | "))
check("screen reader is told which sign is on", "of" in J("document.getElementById('announce').textContent"),
      J("document.getElementById('announce').textContent"))
check("full screen button present with a label", visible("#fullscreen") and J("document.getElementById('fullscreen').getAttribute('aria-label')") == "full screen")

# Upload PDF reveals the document panel (the file chooser itself is the OS's)
J("document.getElementById('pdf-input').click = () => {}; document.getElementById('upload-pdf').click()")
check("Upload PDF shows the document panel", visible("#docpanel") and visible("#sample-pdf"))

# dialogs
J("document.getElementById('about-open').click()"); time.sleep(0.2)
opened = J("document.getElementById('about').open")
key("Escape", "Escape"); time.sleep(0.2)
check("About opens and Escape closes it", opened and not J("document.getElementById('about').open"))

# phone width
c.call("Emulation.setDeviceMetricsOverride", width=390, height=844, deviceScaleFactor=2, mobile=True); time.sleep(0.5)
check("phone: no sideways scroll; Translate button full width",
      not J("document.documentElement.scrollWidth > document.documentElement.clientWidth")
      and J("document.getElementById('sentence-go').getBoundingClientRect().width") > 300)

check("no page errors", not J("window.__errs"), J("window.__errs"))
print("ALL PASS" if ok_all else "SOME FAILED")
proc.kill()
sys.exit(0 if ok_all else 1)
