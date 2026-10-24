"""Minimal Chrome DevTools Protocol driver: no dependencies, raw WebSocket.

Drives a headless Google Chrome for the browser tests. Each run gets a
fresh temporary profile, so no cache or state leaks between runs.
Chrome path: $CHROME, else the standard macOS location."""
import base64, json, os, socket, struct, subprocess, tempfile, time, urllib.request
SC = os.path.dirname(os.path.abspath(__file__))
CHROME = os.environ.get("CHROME", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")

class WS:
    def __init__(self, url):
        rest = url[5:]; hostport, path = rest.split("/", 1); path = "/" + path
        host, port = hostport.split(":")
        self.s = socket.create_connection((host, int(port))); self.s.settimeout(60)
        key = base64.b64encode(os.urandom(16)).decode()
        self.s.sendall((f"GET {path} HTTP/1.1\r\nHost: {hostport}\r\nUpgrade: websocket\r\n"
                        f"Connection: Upgrade\r\nSec-WebSocket-Key: {key}\r\n"
                        f"Sec-WebSocket-Version: 13\r\n\r\n").encode())
        buf = b""
        while b"\r\n\r\n" not in buf: buf += self.s.recv(4096)
        self.buf = buf.split(b"\r\n\r\n", 1)[1]
    def _read(self, n):
        while len(self.buf) < n:
            c = self.s.recv(65536)
            if not c: raise EOFError
            self.buf += c
        out, self.buf = self.buf[:n], self.buf[n:]; return out
    def send(self, text):
        p = text.encode(); h = bytes([0x81]); n = len(p)
        if n < 126: h += bytes([0x80 | n])
        elif n < 65536: h += bytes([0x80 | 126]) + struct.pack(">H", n)
        else: h += bytes([0x80 | 127]) + struct.pack(">Q", n)
        m = os.urandom(4)
        self.s.sendall(h + m + bytes(b ^ m[i % 4] for i, b in enumerate(p)))
    def recv(self):
        data = b""
        while True:
            b0, b1 = self._read(2); fin, op = b0 & 0x80, b0 & 0x0F; n = b1 & 0x7F
            if n == 126: n = struct.unpack(">H", self._read(2))[0]
            elif n == 127: n = struct.unpack(">Q", self._read(8))[0]
            data += self._read(n)
            if fin:
                if op == 0x8: raise EOFError("closed")
                return data.decode()

class CDP:
    def __init__(self, u): self.ws = WS(u); self.id = 0
    def call(self, method, **params):
        self.id += 1; mid = self.id
        self.ws.send(json.dumps({"id": mid, "method": method, "params": params}))
        while True:
            m = json.loads(self.ws.recv())
            if m.get("id") == mid:
                if "error" in m: raise RuntimeError(f"{method}: {m['error']}")
                return m.get("result", {})
    def js(self, e):
        r = self.call("Runtime.evaluate", expression=e, returnByValue=True, awaitPromise=True)
        return r.get("result", {}).get("value")

def launch(port, profile, size="1400,900"):
    proc = subprocess.Popen([CHROME, "--headless=new", "--disable-gpu", "--use-gl=angle",
        "--use-angle=swiftshader", "--hide-scrollbars", "--mute-audio",
        "--autoplay-policy=no-user-gesture-required",
        f"--remote-debugging-port={port}", f"--user-data-dir={tempfile.mkdtemp(prefix=profile + '-')}",
        f"--window-size={size}", "about:blank"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(100):
        try:
            j = json.load(urllib.request.urlopen(f"http://127.0.0.1:{port}/json"))
            pages = [t for t in j if t["type"] == "page"]
            if pages: return proc, CDP(pages[0]["webSocketDebuggerUrl"])
        except Exception: pass
        time.sleep(0.25)
    raise RuntimeError("no devtools target")
