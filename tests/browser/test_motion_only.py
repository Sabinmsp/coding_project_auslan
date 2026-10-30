"""
Browser test: playback from motion data alone, and what each sentence costs.

    python3 tests/browser/test_motion_only.py [port]      # default 8003

Every .mp4 request is BLOCKED, as if the source videos were missing or the
build were motion-only. Needs the app served on that port and Chrome.
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdp import launch  # noqa: E402

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8003
proc, c = launch(9751 + PORT % 10, f"p-motion{PORT}")
for d in ("Page", "Runtime", "Network", "Performance"):
    c.call(f"{d}.enable")
c.call("Network.setCacheDisabled", cacheDisabled=False)
c.call("Network.setBlockedURLs", urls=["*.mp4"])
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


def say(text, timeout=10):
    J(f"auslan.say({text!r})")
    for _ in range(timeout * 10):
        time.sleep(0.1)
        if J("!!(auslan.timeline && auslan.playing && auslan.timeline.plan === auslan.plan)") and J("auslan.plan.text") == text:
            return True
    return False


ink = lambda: J("""(()=>{const c=document.getElementById('canvas');const d=c.getContext('2d').getImageData(0,0,c.width,c.height).data;
  let n=0;for(let i=3;i<d.length;i+=4*97) if(d[i]>8) n++;return n;})()""")
motion_reqs = lambda: J("performance.getEntriesByType('resource').filter(e=>/\\/motion\\/[^/]+\\.json/.test(e.name)).map(e=>[e.name.split('/').pop(), e.transferSize, e.encodedBodySize])")
startup = J("performance.getEntriesByType('resource').concat(performance.getEntriesByType('navigation')).reduce((a,e)=>a+(e.encodedBodySize||0),0)")
print(f"startup payload: {startup/1e3:.0f} KB (as served; hosts that gzip send less)")

# I LOVE AUSTRALIA: parse, match, resolve ids, load only those, play, label
before = len(motion_reqs())
played = say("I LOVE AUSTRALIA")
steps = J("auslan.plan.steps.map(s=>s.kind==='sign'?s.id:s.kind)")
time.sleep(1.0)
reqs = motion_reqs()[before:]
check("I LOVE AUSTRALIA: plans three signs and plays them without any MP4",
      played and steps == ["i", "love", "australia"] and ink() > 150, f"{steps}, ink {ink()}")
check("  only that sentence's motion files were downloaded", len(reqs) == 3, [r[0] for r in reqs])
sentence_kb = sum(r[2] for r in reqs) / 1e3
print(f"  download for this sentence: {sentence_kb:.0f} KB of motion JSON (as served)")
check("  active sign label follows playback", J("document.getElementById('word').textContent") in ("I", "Love", "Australia"),
      J("document.getElementById('word').textContent"))
check("  the video panel says the source video is unavailable",
      "unavailable" in J("document.getElementById('refnote').textContent")
      or J("document.getElementById('reference').closest('section').hidden"))

# paused with no video: no busy waiting
J("document.getElementById('play').click()"); time.sleep(0.3)
m = lambda: next(x["value"] for x in c.call("Performance.getMetrics")["metrics"] if x["name"] == "ScriptDuration")
a = m(); time.sleep(2); b = m()
check("  paused without a video: the page goes idle", (b - a) * 500 < 6, f"{(b - a) * 500:.1f} ms script per second")

# single sign, multi-word gloss, sequence, fingerspelling
check("single known sign", say("hello") and J("auslan.plan.steps.length") == 1)
check("multi-word gloss is ONE sign", say("thank you") and J("auslan.plan.steps.map(s=>s.id)") == ["thank-you"])
check("several signs in sequence", say("hello doctor thank you") and J("auslan.timeline.clips.length") == 3)
check("fingerspelling fallback for an unknown word", say("zxqv")
      and J("auslan.plan.steps[0].kind") == "spell" and J("auslan.timeline.clips.length") == 4)

# cache: a repeated sentence costs nothing new
n0 = len(motion_reqs()); say("hello doctor thank you"); time.sleep(0.5)
check("cached: replaying a sentence downloads nothing again", len(motion_reqs()) == n0, len(motion_reqs()) - n0)

# pause / replay / speed
J("document.getElementById('play').click()"); time.sleep(0.2); tp = J("auslan.t"); time.sleep(0.4)
check("pause holds the frame", abs(J("auslan.t") - tp) < 1e-9)
J("document.getElementById('replay').click()"); time.sleep(0.2)
check("replay restarts from the beginning", J("auslan.playing") and J("auslan.t") < 0.5)
J("document.getElementById('speed').value='0.5'; document.getElementById('speed').dispatchEvent(new Event('change'))")
a = J("[auslan.t, performance.now()]"); time.sleep(0.6); b = J("[auslan.t, performance.now()]")
rate = (b[0] - a[0]) / ((b[1] - a[1]) / 1000)
check("speed 0.5x", 0.4 < rate < 0.6 or rate < 0, f"{rate:.2f}x")
J("document.getElementById('speed').value='1'; document.getElementById('speed').dispatchEvent(new Event('change'))")

# a failed motion request: reported, the rest plays
clip = J("auslan.lib.manifest.signs['doctor'].clip")
c.call("Network.setBlockedURLs", urls=["*.mp4", f"*motion/{clip}.json"])
J("auslan.lib.cache.map.clear()")
played = say("hello doctor")
check("failed motion request: reported, the rest still plays",
      played and "could not load: DOCTOR" in J("document.getElementById('plan-notes').textContent")
      and J("auslan.timeline.clips.length") == 1)

check("no page errors", not J("window.__errs"), J("window.__errs"))
print("ALL PASS" if ok_all else "SOME FAILED")
proc.kill()
sys.exit(0 if ok_all else 1)
