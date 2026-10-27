"""
Vercel serverless function for POST /api/summarize (the optional AI summary).
scripts/build_dist.py copies this to dist/api/summarize.py, and
backend/summarize_llm.py next to it as dist/api/_summarize_llm.py.
Set ANTHROPIC_API_KEY in the Vercel project's environment variables;
without it the endpoint answers 503 and the page uses its offline summary.
"""
import json
import os
import sys
from http.server import BaseHTTPRequestHandler

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _summarize_llm import handle_post  # noqa: E402


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        status, out = handle_post(self.rfile.read(min(n, 2_000_000)))
        data = json.dumps(out).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)
