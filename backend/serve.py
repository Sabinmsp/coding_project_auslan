"""
Local dev server:
    python3 backend/serve.py              # http://localhost:8001 -- the app
    python3 backend/serve.py 8002 dist    # serve one folder as-is (the built bundle)

In development the app is frontend/ and its runtime data is assets/; this
serves frontend/ at / and mounts assets/ at /assets/, which is exactly the
layout scripts/build_dist.py produces -- so the page uses the same URLs in
development and when deployed.

Use this instead of `python3 -m http.server`, which ignores HTTP Range
requests. Browsers seek inside an mp4 by asking for a byte range; served
the whole file with a 200 instead, Chrome cannot seek in a video it has
not fully cached, so scrubbing leaves the source video stuck at 0 while
the figure moves. Static hosts (Netlify, GitHub Pages, ...) handle ranges
already -- this is only for running locally.

Also sends no-cache for .js/.json, so a rebuilt manifest or an edited
module is picked up on reload instead of served stale.
"""
import json
import os
import re
import sys
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend import paths  # noqa: E402


class RangeHandler(SimpleHTTPRequestHandler):
    mounts = {}          # URL prefix -> directory, checked before the root

    def translate_path(self, path):
        for prefix, directory in self.mounts.items():
            if path.startswith(prefix):
                saved = self.directory
                self.directory = directory      # reuse the stdlib's path sanitising
                try:
                    return super().translate_path("/" + path[len(prefix):])
                finally:
                    self.directory = saved
        return super().translate_path(path)

    def end_headers(self):
        if self.path.split("?")[0].endswith((".js", ".json", ".html", "/")):
            self.send_header("Cache-Control", "no-cache")
        self.send_header("Accept-Ranges", "bytes")
        super().end_headers()

    def send_head(self):
        m = re.match(r"bytes=(\d*)-(\d*)$", self.headers.get("Range", ""))
        path = self.translate_path(self.path)
        if not m or not os.path.isfile(path):
            return super().send_head()
        size = os.path.getsize(path)
        start = int(m.group(1)) if m.group(1) else max(0, size - int(m.group(2) or 0))
        end = int(m.group(2)) if m.group(1) and m.group(2) else size - 1
        end = min(end, size - 1)
        if start > end:
            self.send_error(416, "Requested Range Not Satisfiable")
            return None
        f = open(path, "rb")
        f.seek(start)
        self.send_response(206)
        self.send_header("Content-Type", self.guess_type(path))
        self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.send_header("Content-Length", str(end - start + 1))
        self.end_headers()
        self._remaining = end - start + 1
        return f

    def copyfile(self, source, outputfile):
        remaining = getattr(self, "_remaining", None)
        if remaining is None:
            return super().copyfile(source, outputfile)
        while remaining > 0:
            chunk = source.read(min(65536, remaining))
            if not chunk:
                break
            outputfile.write(chunk)
            remaining -= len(chunk)
        self._remaining = None

    def do_POST(self):
        # the only dynamic route: the optional AI summary (backend/summarize_llm.py)
        if self.path.split("?")[0] != "/api/summarize":
            self.send_error(404)
            return
        from backend.summarize_llm import handle_post
        n = int(self.headers.get("Content-Length") or 0)
        status, out = handle_post(self.rfile.read(min(n, 2_000_000)))
        data = json.dumps(out).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8001
    if len(sys.argv) > 2:                       # one folder, as-is (e.g. dist/)
        root = Path(sys.argv[2]).resolve()
    else:                                       # development: app + /assets/ mount
        root = paths.FRONTEND
        RangeHandler.mounts = {"/assets/": str(paths.ASSETS)}
    handler = partial(RangeHandler, directory=str(root))
    print(f"serving {root} on http://localhost:{port}"
          + (f"  (+ {paths.ASSETS} at /assets/)" if RangeHandler.mounts else "")
          + "  -- Ctrl-C to stop")
    ThreadingHTTPServer(("", port), handler).serve_forever()
