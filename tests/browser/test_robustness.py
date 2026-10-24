"""
Browser robustness test: failure paths and playback edge cases.

    python3 tests/browser/test_robustness.py [port]      # default 8003

Needs the app served on that port and Google Chrome. Exit code 1 on failure.
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdp import launch  # noqa: E402

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8003
proc, c = launch(9771 + PORT % 10, f"p-robust{PORT}")
for d in ("Page", "Runtime", "Network"):
    c.call(f"{d}.enable")
c.call("Network.setCacheDisabled", cacheDisabled=True)
c.call("Page.addScriptToEvaluateOnNewDocument", source="""
  window.__errs = [];
  addEventListener('error', e => __errs.push('error: ' + e.message));
  addEventListener('unhandledrejection', e => __errs.push('rejection: ' + (e.reason && e.reason.message || e.reason)));""")
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


def load(blocked=()):
    c.call("Network.setBlockedURLs", urls=list(blocked))
    c.call("Page.navigate", url=f"http://localhost:{PORT}/")
    for _ in range(80):
        time.sleep(0.25)
        if J("!!(window.auslan && auslan.lib)"):
            return


load()
manifest_clip = lambda sid: J(f"auslan.lib.manifest.signs[{sid!r}].clip")
shape = lambda: J("auslan.plan.steps.map(s=>s.kind==='sign'?s.id:s.kind==='spell'?'fs:'+s.letters.join(''):'-'+s.en).join(' ')")

# ---- missing animation file mid-sentence ---------------------------------
doctor = manifest_clip("doctor")
load(blocked=[f"*assets/signs/motion/{doctor}.json"])
J("auslan.say('hello doctor thank you')")
playing = wait_playing()
notes = J("document.getElementById('plan-notes').textContent")
steps_in_tl = J("[...new Set(auslan.timeline.clips.map(c=>auslan.plan.steps[c.step].id))].join(' ')")
check("missing motion file: the rest of the sentence still plays", playing and steps_in_tl == "hello thank-you", steps_in_tl)
check("missing motion file: the failure is reported to the viewer", "could not load: DOCTOR" in notes, notes[-60:])
check("missing motion file: no page errors", not J("window.__errs"), J("window.__errs"))
load()

# ---- rapid switching between sentences -----------------------------------
J("auslan.say('hello doctor'); auslan.say('thank you'); auslan.say('I can help')")
wait_playing(); time.sleep(0.8)
plan_text = J("auslan.plan.text")
clip_steps_ok = J("auslan.timeline.clips.every(c => { const s = auslan.plan.steps[c.step]; "
                  "return s && (s.kind !== 'sign' || c.id === s.id) })")
check("rapid switching: only the last sentence is shown", plan_text == "I can help" and clip_steps_ok, plan_text)
src = J("document.getElementById('reference').currentSrc.split('/').pop()")
clip_videos = J("auslan.timeline.clips.map(c=>c.video.split('/').pop())")
check("rapid switching: the video belongs to the last sentence", src in clip_videos, src)

# ---- pause during a transition --------------------------------------------
J("auslan.say('hello doctor')"); wait_playing()
gap = J("(()=>{const g=auslan.timeline.items.find(i=>i.type==='gap'&&!i.wrap);return (g.t0+g.t1)/2})()")
J(f"auslan.seek({gap})"); time.sleep(0.5)
ink = J("""(()=>{const c=document.getElementById('canvas');const d=c.getContext('2d').getImageData(0,0,c.width,c.height).data;
            let n=0;for(let i=3;i<d.length;i+=4*97) if(d[i]>8) n++;return n;})()""")
check("pause in a transition: figure drawn, playback and video paused",
      not J("auslan.playing") and ink > 100 and J("document.getElementById('reference').paused"), f"ink {ink}")
J("document.getElementById('play').click()"); time.sleep(0.6)
check("resume from a transition: time moves on from the pause point",
      J("auslan.playing") and J("auslan.t") > gap, f"{gap:.2f}s -> {J('auslan.t'):.2f}s")

# ---- unreliable sign filtering (every route) -------------------------------
unreliable = J("Object.entries(auslan.lib.manifest.signs).find(([id,s])=>s.status==='unreliable' && s.keys[0].split(' ').length===1)")
uid, ukey = unreliable[0], unreliable[1]["keys"][0].lower()
J(f"auslan.say({ukey!r})"); wait_playing(); time.sleep(0.3)
check(f"unreliable ({uid}) typed: fingerspelled", J("auslan.plan.steps[0].kind") == "spell", shape())
J(f"auslan.gloss({uid!r})"); wait_playing(); time.sleep(0.3)
check("unreliable in a gloss line: fingerspelled", J("auslan.plan.steps[0].kind") == "spell", shape())
check("unreliable not playing: no warning shown", J("document.getElementById('warn').hidden"))
J(f"auslan.edit(0, 'sign:{uid}')"); wait_playing(); time.sleep(0.6)
check("unreliable chosen from the menu: plays WITH a visible warning",
      J("auslan.plan.steps[0].kind") == "sign" and not J("document.getElementById('warn').hidden"),
      J("document.getElementById('warn').textContent")[:60])
J("auslan.say('hello')"); wait_playing(); time.sleep(0.5)
check("warning disappears with the next sentence", J("document.getElementById('warn').hidden"))

# ---- fingerspelling fallback ------------------------------------------------
J("auslan.say('zxqv')"); wait_playing(); time.sleep(0.4)
check("fingerspelling fallback: one clip per letter, labelled",
      J("auslan.timeline.clips.length") == 4 and J("document.getElementById('sub').textContent").startswith("✋ Fingerspelled"),
      J("document.getElementById('sub').textContent"))

# ---- playback continuity ----------------------------------------------------
J("auslan.say('hello doctor thank you')"); wait_playing()
times = []
for _ in range(20):
    times.append(J("auslan.t")); time.sleep(0.1)
steps = [b - a for a, b in zip(times, times[1:])]
check("playback continuity: the clock never stalls or goes back (except at the loop)",
      sum(1 for s in steps if s <= 0) <= 1, f"min step {min(steps):.3f}s")

check("no page errors", not J("window.__errs"), J("window.__errs"))
print("ALL PASS" if ok_all else "SOME FAILED")
proc.kill()
sys.exit(0 if ok_all else 1)
