"""
Browser test: PDF -> key points -> sign a point, in real Chrome.

    python3 tests/browser/test_document.py [port]      # default 8003

Needs the app served on that port and Google Chrome. Exit code 1 on failure.
"""
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from cdp import launch  # noqa: E402

FIX = os.path.join(HERE, "..", "fixtures")
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8003
proc, c = launch(9741 + PORT % 10, f"p-doc{PORT}")
for d in ("Page", "Runtime", "DOM"):
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


def settle(timeout=40):
    """until the document flow has finished (points shown and no AI request pending, or an error)"""
    for _ in range(timeout * 10):
        time.sleep(0.1)
        msg = J("document.getElementById('docmsg').textContent")
        if J("document.getElementById('docmsg').classList.contains('error')"):
            return
        if J("auslan.points.length") and not msg.startswith(("Asking", "Reading", "Opening")):
            return


def upload(name):
    root = c.call("DOM.getDocument")["root"]["nodeId"]
    node = c.call("DOM.querySelector", nodeId=root, selector="#pdf-input")["nodeId"]
    c.call("DOM.setFileInputFiles", nodeId=node, files=[os.path.abspath(os.path.join(FIX, name))])


def wait_playing(text, timeout=10):
    for _ in range(timeout * 10):
        time.sleep(0.1)
        if J("!!(auslan.timeline && auslan.playing && auslan.timeline.plan === auslan.plan)") and J("auslan.plan.text") == text:
            return True
    return False


# short PDF via the sample button
J("document.getElementById('sample-pdf').click()"); settle()
pts = J("auslan.points")
check("short PDF (sample): key points with page numbers", 5 <= len(pts) <= 10 and all(p["pages"] for p in pts),
      f"{len(pts)} points; {J('document.getElementById(`docstats`).textContent')[:60]}")
check("  facts kept: the enrolment deadline is a point", any("14 February 2027" in p["simple"] for p in pts))
msg = J("document.getElementById('docmsg').textContent")
check("  AI unavailable -> says so, offline summary stays", "offline summary" in msg or msg == "", msg[:80])

# select a point -> it is planned and played
J("document.querySelector('#points .pt').click()")
first = pts[0]["simple"]
check("selecting a key point signs it", wait_playing(first), J("auslan.plan.text")[:60])
check("  the point is highlighted and shown as English under the figure",
      J("document.querySelector('#points li.active') !== null") and J("document.querySelectorAll('#sentence .w').length") > 3)

# medium PDF via the file input
t = time.time(); upload("handbook_long.pdf"); settle()
stats = J("document.getElementById('docstats').textContent")
check("medium PDF (13 pages): read and summarised", "13 pages" in stats and len(J("auslan.points")) == 10,
      f"{stats[:60]} in {time.time() - t:.1f}s")
check("  running header removed from the text",
      not any("Student Handbook 2027" in p["simple"] for p in J("auslan.points")))

# invalid and text-free files
upload("not_a_pdf.pdf"); settle(5)
check("invalid file: clear message, no points", "not a PDF" in J("document.getElementById('docmsg').textContent")
      and J("auslan.points.length") == 0)
upload("handbook_blank.pdf"); settle(10)
check("PDF without text: says it may be scanned", "scanned" in J("document.getElementById('docmsg').textContent"),
      J("document.getElementById('docmsg').textContent")[:60])

# the three test sentences: supported signs play, missing ones are labelled, nothing freezes
for text in ["Welcome to the university.", "Students must attend classes.", "The examination starts tomorrow."]:
    J(f"auslan.say({text!r})")
    played = wait_playing(text)
    t0 = J("auslan.t"); time.sleep(0.5)
    signs = J("auslan.plan.steps.filter(s=>s.kind==='sign').map(s=>s.gloss).join(' ')")
    check(f"'{text}' plays (signs: {signs})", played and J("auslan.t") != t0)

check("no page errors", not J("window.__errs"), J("window.__errs"))
print("ALL PASS" if ok_all else "SOME FAILED")
proc.kill()
sys.exit(0 if ok_all else 1)
