"""
Browser behaviour test: the main user workflows in a real (headless) Chrome.

    python3 tests/browser/test_behaviour.py [port]      # default 8003

Needs the app served on that port (python3 backend/serve.py 8003) and
Google Chrome. Prints PASS/FAIL per check; exit code 1 if any failed.
"""
import base64, json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdp import launch
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8003
proc, c = launch(9761 + PORT % 10, f"p-plan{PORT}")
for d in ("Page", "Runtime", "Network"): c.call(f"{d}.enable")
c.call("Network.setCacheDisabled", cacheDisabled=True)
c.call("Page.addScriptToEvaluateOnNewDocument", source="""
  window.__errs = [];
  addEventListener('error', e => __errs.push('error: ' + e.message));
  addEventListener('unhandledrejection', e => __errs.push('rejection: ' + (e.reason && e.reason.message || e.reason)));
  const ce = console.error; console.error = (...a) => { __errs.push('console: ' + a.join(' ')); ce(...a); };""")
c.call("Page.navigate", url=f"http://localhost:{PORT}/index.html")
for _ in range(80):
    time.sleep(0.25)
    if c.js("!!(window.auslan && auslan.lib && document.querySelectorAll('#words button').length)"): break
J = c.js
ok_all = True
def check(name, cond, detail=""):
    global ok_all
    ok_all &= bool(cond)
    print(("PASS " if cond else "FAIL ") + name + (f"   [{detail}]" if detail else ""))
def wait_tl(timeout=8):
    for _ in range(int(timeout / 0.1)):
        if J("!!(auslan.timeline && auslan.playing)"): return True
        time.sleep(0.1)
    return False
ink = lambda: J("""(()=>{const c=document.getElementById('canvas');const x=c.getContext('2d');
  const d=x.getImageData(0,0,c.width,c.height).data;let n=0;for(let i=3;i<d.length;i+=4*97) if(d[i]>8) n++;return n;})()""")
shape = lambda: J("auslan.plan.steps.map(s=>s.kind==='sign'?s.id:s.kind==='spell'?'fs:'+s.letters.join(''):s.kind==='phrase'?'phrase:'+s.id:'-'+s.en).join(' ')")

print("libstat:", J("document.getElementById('libstat').textContent"))

# 1 one known word (quick pick)
J("auslan.quick('HELLO')"); wait_tl(); time.sleep(0.8)
check("1 quick pick HELLO plays", J("auslan.plan.steps[0].id") == "hello" and ink() > 200,
      f"ink {ink()}, video {J('document.getElementById(`reference`).currentSrc.split(`/`).pop()')}")
for _ in range(30):                     # up to 3 s: right after a disk-heavy suite the first load is slower
    if J("document.getElementById('reference').readyState") >= 2: break
    time.sleep(0.1)
check("  source video loaded & in step", J("document.getElementById('reference').readyState") >= 2)
check("  face drawn from landmarks", J("auslan.timeline.clips[0].motion.frames.some(f=>f.face)"))

# 3 name + 2 multiple known
J("auslan.say('Hello, my name is Sabin.')"); wait_tl()
check("3 name sentence plan", shape() == "hello my fs:NAME -is fs:SABIN", shape())
check("  clips = 1+1+4+5 letters", J("auslan.timeline.clips.length") == 11, J("auslan.timeline.clips.length"))
seen = set()
for _ in range(40):
    time.sleep(0.15); seen.add(J("auslan.activeStep"))
check("  captions walk through the steps", {0, 1, 2} <= seen, sorted(seen))
check("  English word highlighted", J("document.querySelector('#sentence .w.active') !== null"))

# negation + time-first
J("auslan.say(\"I don't want to pay the bill tomorrow\")"); wait_tl()
check("negation + time first", shape().startswith("tomorrow i -don't not fs:WANT") or shape().startswith("tomorrow i -don't want-not-want"), shape())

# wh-question
J("auslan.say('Who is your doctor?')"); wait_tl()
check("wh-question: wh last + facial grammar stated", shape().endswith("who") and
      "NOT expressed" in J("document.getElementById('plan-notes').textContent"), shape())

# 4 unknown + human correction
J("auslan.say('I can help')"); wait_tl()
st = J("auslan.plan.steps[1]")
check("CAN (TIN) not signed for modal 'can' (ABLE via the dictionary, or spelled)",
      st.get("id") != "can-tin" and (st.get("id") == "able" or st["kind"] == "spell"), st.get("id") or st["kind"])
J("auslan.edit(1, 'omit')"); wait_tl()
check("reviewer edit -> omitted, marked reviewed, replays",
      shape().split()[1] == "-can" and J("document.querySelector('#plan .chip.reviewed') !== null"), shape())

# gloss line validation
J("auslan.gloss('hello fs:SABIN bogus-sign')"); wait_tl()
check("gloss line: unknown id fingerspelled + reported", shape() == "hello fs:SABIN fs:BOGUSSIGN" and
      "no such sign" in J("document.getElementById('plan-notes').textContent"), shape())

# pre-stitched phrase still works
J("auslan.quick('SABIN')"); wait_tl(); time.sleep(0.6)
check("existing SABIN phrase plays with letter progress", J("document.getElementById('word').textContent") == "SABIN"
      and "–" in J("document.getElementById('sub').textContent"), J("document.getElementById('sub').textContent"))

# 9 speed / scrub / replay / loop
J("auslan.quick('HELLO')"); wait_tl()
J("document.getElementById('speed').value='0.5'; document.getElementById('speed').dispatchEvent(new Event('change'))")
J("document.getElementById('replay').click()"); t0 = J("auslan.t"); time.sleep(1.0); t1 = J("auslan.t")
check("speed 0.5x halves the clock", 0.35 < t1 - t0 < 0.65, f"{t1 - t0:.2f}s timeline per 1s")
J("document.getElementById('speed').value='1'; document.getElementById('speed').dispatchEvent(new Event('change'))")
J("auslan.seek(0.9)"); time.sleep(0.5)
vt = J("document.getElementById('reference').currentTime"); exp = J("(()=>{const c=auslan.timeline.clips[0];return (c.span[0]+Math.floor(0.9*c.motion.fps))/c.motion.fps})()")
check("scrub pauses figure + video and aligns them", not J("auslan.playing") and abs(vt - exp) < 0.05, f"video {vt:.3f} vs {exp:.3f}")
J("document.getElementById('loop').checked=false"); J("document.getElementById('replay').click()")
time.sleep(J("auslan.timeline.duration") + 0.6)
check("loop off: stops at end", not J("auslan.playing") and abs(J("auslan.t") - J("auslan.timeline.duration")) < 1e-6)
J("document.getElementById('loop').checked=true")

# pause / resume with the Play button
J("document.getElementById('loop').checked=true")
J("auslan.say('thank you doctor')"); wait_tl(); time.sleep(0.6)
J("document.getElementById('play').click()"); time.sleep(0.15)
tp = J("auslan.t"); time.sleep(0.6)
paused_ok = (not J("auslan.playing")) and abs(J("auslan.t") - tp) < 1e-9 and J("document.getElementById('reference').paused")
# measured with the PAGE's clock, so a slow test machine can't fake a jump:
# right after Play, t must continue from tp, then advance at 1 s per second
a = J("(()=>{document.getElementById('play').click(); return [auslan.t, performance.now()]})()")
time.sleep(0.5)
b = J("[auslan.t, performance.now()]")
rate = (b[0] - a[0]) / ((b[1] - a[1]) / 1000)
resumed = J("auslan.playing") and abs(a[0] - tp) < 0.05 and 0.8 < rate < 1.2
check("pause freezes figure + video; play resumes from the same point", paused_ok and resumed,
      f"paused at {tp:.2f}s, resumed from {a[0]:.2f}s at {rate:.2f}x")

# 8 repeated signs
J("auslan.say('hello hello')"); wait_tl()
check("8 repeated sign -> two clips", J("auslan.timeline.clips.length") == 2 and shape() == "hello hello")

# 7 long sentence
long = ". ".join(["I will pay the bill tomorrow and help my mother"] * 6)
t = time.time(); J(f"auslan.say({json.dumps(long)})"); okl = wait_tl(20)
check("7 long sentence plays", okl, f"{J('auslan.plan.steps.length')} steps, {J('auslan.timeline.clips.length')} clips, "
      f"{J('auslan.timeline.duration'):.1f}s, ready in {time.time()-t:.1f}s")
check("  lazy loading + cache: distinct signs fetched once",
      J("auslan.lib.cache.size") <= 60, f"cache {J('auslan.lib.cache.size')}")

# real typing: a space in the input must be a space
J("const i=document.getElementById('sentence-input'); i.value=''; i.focus()")
for ch in "hi you":
    c.call("Input.dispatchKeyEvent", type="keyDown", key=ch, text=ch,
           code="Space" if ch == " " else f"Key{ch.upper()}", windowsVirtualKeyCode=32 if ch == " " else ord(ch.upper()))
    c.call("Input.dispatchKeyEvent", type="keyUp", key=ch, code="Space" if ch == " " else f"Key{ch.upper()}")
check("typing a space into the input works", J("document.getElementById('sentence-input').value") == "hi you",
      repr(J("document.getElementById('sentence-input').value")))

# screenshot for a visual check
J("auslan.say('Thank you doctor, I will pay the bill tomorrow')"); wait_tl(); time.sleep(1.2)
J("auslan.seek(1.0)"); time.sleep(0.6)

errs = J("window.__errs")
check("no page errors", not errs, errs)
print("ALL PASS" if ok_all else "SOME FAILED")
proc.kill()
sys.exit(0 if ok_all else 1)
