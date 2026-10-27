"""
Browser stress test: rapid input, repeated play/pause, a long sentence, memory,
and a SLOW DEVICE (CPU throttled to 1/4 speed).

    python3 tests/browser/test_stress.py [port]      # default 8003
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdp import launch  # noqa: E402

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8003
proc, c = launch(9721 + PORT % 10, f"p-stress{PORT}")
for d in ("Page", "Runtime", "Performance"):
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


def wait_for(expr, timeout=15):
    for _ in range(int(timeout / 0.1)):
        if J(expr):
            return True
        time.sleep(0.1)
    return False


SENTENCES = ["hello", "thank you doctor", "I need help", "please pay your bill tomorrow", "where is the hospital",
             "my name is Sabin", "I love Australia", "welcome to the university", "students must attend classes",
             "the examination starts tomorrow"]

# ---- rapid translations: 40 requests in a burst, only the last one survives
J("for (let i = 0; i < 40; i++) auslan.say(%r[i %% %d] + (i === 39 ? ' final' : ''))" % (SENTENCES, len(SENTENCES)))
ready = wait_for("!!(auslan.timeline && auslan.playing && auslan.timeline.plan === auslan.plan)")
time.sleep(0.5)
check("40 rapid translations: the last request wins and is what plays",
      ready and J("auslan.plan.text").endswith("final") and J("auslan.timeline.plan === auslan.plan")
      and J("auslan.timeline.clips.every(c => { const s = auslan.plan.steps[c.step]; return s && (s.kind !== 'sign' || c.id === s.id) })"),
      J("auslan.plan.text"))
check("  no page errors", not J("window.__errs"), J("window.__errs"))

# ---- repeated play/pause: 101 clicks end up playing, clock never jumps
J("auslan.say('hello doctor thank you')"); wait_for("!!(auslan.timeline && auslan.playing)")
J("document.getElementById('play').click()")
t0 = J("auslan.t")
J("for (let i = 0; i < 100; i++) document.getElementById('play').click()")    # 100 more: even -> paused stays paused
time.sleep(0.3)
check("101 play/pause clicks: ends paused, position unchanged", not J("auslan.playing") and abs(J("auslan.t") - t0) < 1e-9)
J("document.getElementById('play').click()"); time.sleep(0.6)
check("  and resumes from the same place", J("auslan.playing") and J("auslan.t") > t0)

# ---- long sentence: plays and keeps one clock
long = " ".join(["I will pay the bill tomorrow and help my mother."] * 8)
t = time.time(); J("auslan.say(%r)" % long)
ok = wait_for("!!(auslan.timeline && auslan.playing && auslan.timeline.plan === auslan.plan)", 30)
check("long sentence (8 sentences, ~70 words) plays", ok,
      f"{J('auslan.plan.steps.length')} steps, {J('auslan.timeline.duration'):.0f}s long, ready in {time.time() - t:.1f}s")
check("  planned per sentence", J("auslan.plan.sentences") == 8, J("auslan.plan.sentences"))

# ---- memory: 60 different sentences keep the cache bounded and the heap small
heap0 = J("performance.memory.usedJSHeapSize") / 1e6
for i in range(60):
    J("auslan.say(%r[%d %% %d] + ' %d')" % (SENTENCES, i, len(SENTENCES), i)); time.sleep(0.12)
wait_for("!!(auslan.timeline && auslan.playing)")
heap1 = J("performance.memory.usedJSHeapSize") / 1e6
check("60 more sentences: cache bounded (<= 80 signs), heap growth modest",
      J("auslan.lib.cache.size") <= 80 and heap1 - heap0 < 120, f"cache {J('auslan.lib.cache.size')}, heap {heap0:.0f} -> {heap1:.0f} MB")

# ---- slow device: CPU at 1/4 speed
c.call("Emulation.setCPUThrottlingRate", rate=4)
J("auslan.say('please pay your bill tomorrow')")
wait_for("!!(auslan.timeline && auslan.playing && auslan.timeline.plan === auslan.plan)", 30)
J("window.__f = []; (function f(t) { __f.push(t); if (__f.length < 300) requestAnimationFrame(f) })(performance.now())")
a = J("[auslan.t, performance.now()]"); time.sleep(2.0); b = J("[auslan.t, performance.now()]")
rate = (b[0] - a[0]) / ((b[1] - a[1]) / 1000)
gaps = sorted(J("__f.slice(1).map((t, i) => t - __f[i])") or [16])
fps = 1000 / gaps[len(gaps) // 2]
check("slow device (CPU 1/4): the clock still runs at real time", 0.85 < rate < 1.15 or rate < 0, f"{rate:.2f}x real time, median frame {gaps[len(gaps)//2]:.0f} ms (~{fps:.0f} fps)")
J("auslan.seek(1.0)"); time.sleep(0.3)
check("  scrubbing still lands where asked", abs(J("auslan.t") - 1.0) < 1e-6)
J("auslan.say('hello')"); check("  a new sentence still plays", wait_for("!!(auslan.timeline && auslan.playing && auslan.timeline.plan === auslan.plan)", 30))
c.call("Emulation.setCPUThrottlingRate", rate=1)

check("no page errors at the end", not J("window.__errs"), J("window.__errs"))
print("ALL PASS" if ok_all else "SOME FAILED")
proc.kill()
sys.exit(0 if ok_all else 1)
