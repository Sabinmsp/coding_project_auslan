"""
Make the test PDFs: a FICTIONAL student handbook (no real institution), short
and long, printed by headless Chrome with a running header and page numbers
so the clean-up has real page furniture to remove.

    python3 tests/fixtures/make_pdfs.py      # writes tests/fixtures/handbook_*.pdf

Re-run only if you change the text; the PDFs are committed.
"""
import base64
import html
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "browser"))
from cdp import launch  # noqa: E402

CORE = [
    ("Welcome", [
        "Welcome to the university. This handbook explains what you need to know in your first year.",
        "Please read it carefully and keep it for reference during your studies.",
    ]),
    ("Enrolment", [
        "You must complete your enrolment online no later than 14 February 2027.",
        "Students who enrol late may not be able to choose their preferred classes.",
        "If you need assistance with enrolment, contact Student Central on 08 8946 0000 or at studentcentral@example.edu.",
    ]),
    ("Attendance", [
        "Students must attend classes and tutorials for every unit in which they are enrolled.",
        "If you miss more than three tutorials without a reason, your lecturer may contact you.",
        "Lectures are recorded, but recordings are not a replacement for attending tutorials.",
    ]),
    ("Assessment", [
        "Each unit has at least two assessment tasks, which are listed in the unit outline.",
        "Assignments are required to be submitted through the learning portal by 11:59 pm on the due date.",
        "Late assignments lose 5% of the available marks for each day they are late.",
        "You may apply for an extension prior to the due date if you are ill or have a family emergency.",
    ]),
    ("Examinations", [
        "The examination starts tomorrow at 9:00 am in the Main Hall.",
        "The final examination period commences on 2 June 2027 and ends on 13 June 2027.",
        "Bring your student card to every examination; you cannot enter the room without it.",
        "Mobile phones are not permitted in the examination room.",
    ]),
    ("Fees", [
        "Your tuition fees are due on 31 March 2027.",
        "If you cannot pay your fees by the due date, please contact the fees office to discuss a payment plan.",
    ]),
    ("Support", [
        "The accessibility service can arrange Auslan interpreters, live captioning and note-takers.",
        "To obtain these services, register with the accessibility service at least two weeks before classes begin.",
        "Free counselling is available to all students; appointments can be booked online.",
    ]),
]

FILLER = [
    "This unit introduces the main ideas of the discipline and how they are applied in practice.",
    "Weekly readings are available in the library and on the learning portal.",
    "Tutorials give you a chance to discuss the readings in small groups with a tutor.",
    "Your tutor will give you feedback on your work within three weeks of submission.",
    "Academic integrity means that the work you submit must be your own.",
    "Group work should be shared fairly between all members of the group.",
    "The unit coordinator is your first contact for questions about the unit.",
    "Field trips are optional and are announced at least one week in advance.",
]


def page_html(sections):
    body = []
    for title, paras in sections:
        body.append(f"<h2>{html.escape(title)}</h2>")
        body += [f"<p>{html.escape(p)}</p>" for p in paras]
    return ("<!doctype html><meta charset=utf-8><style>body{font:12pt Georgia,serif;margin:0 1cm}"
            "h1{font-size:20pt}h2{font-size:14pt;margin-top:18pt}.pb{break-before:page}</style>"
            "<h1>Example University Student Handbook</h1><p><i>A fictional sample document for testing.</i></p>"
            + "\n".join(body))


def long_sections():
    out = list(CORE)
    for u in range(1, 41):
        paras = [f"Unit EX{100 + u} runs in semester {1 + u % 2} and is worth 10 credit points."]
        paras += [FILLER[(u + k) % len(FILLER)] for k in range(5)]
        out.append((f"Unit guide EX{100 + u}", paras))
    return out


def main():
    proc, c = launch(9799, "p-fixtures")
    c.call("Page.enable")
    for name, sections in (("short", CORE), ("long", long_sections()), ("blank", None)):
        doc = page_html(sections) if sections else None
        if not sections:                        # a PDF with no text (like a scanned document)
            doc = "<!doctype html><svg width=400 height=300><rect width=400 height=300 fill=#ccc /></svg>"
        c.call("Page.navigate", url="data:text/html;base64," + base64.b64encode(doc.encode()).decode())
        import time
        time.sleep(1.0)
        pdf = c.call("Page.printToPDF", displayHeaderFooter=bool(sections), printBackground=False,
                     headerTemplate="<div style='font-size:8pt;width:100%;text-align:center'>Example University Student Handbook 2027</div>",
                     footerTemplate="<div style='font-size:8pt;width:100%;text-align:center'>Page <span class=pageNumber></span></div>",
                     marginTop=0.8, marginBottom=0.8)["data"]
        path = os.path.join(HERE, f"handbook_{name}.pdf")
        with open(path, "wb") as f:
            f.write(base64.b64decode(pdf))
        print(path, os.path.getsize(path), "bytes")
    proc.kill()


if __name__ == "__main__":
    main()
