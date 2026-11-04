#!/usr/bin/env python3
"""Tiny RFB (VNC) client for driving a Proxmox VM's console - stdlib only.

Transports:
  * Proxmox API: POST .../qemu/<vmid>/vncproxy (websocket=1) then RFB over the
    .../vncwebsocket endpoint (same path noVNC uses). Works with an API token or
    a ticket cookie and needs only VM.Console on the VM - no root, no `qm`.
  * unix socket (/var/run/qemu-server/<vmid>.vnc) - root-only, for local tests.

Capabilities: screenshot (raw 32bpp framebuffer -> PNG), key events (X11
keysyms), absolute pointer events (usb-tablet), simple pixel/region probes.
"""
import base64
import json
import os
import socket
import ssl
import struct
import sys
import time
import urllib.parse
import urllib.request
import zlib

from vncdes import vnc_encrypt_challenge

KEYSYMS = {
    "ret": 0xFF0D, "enter": 0xFF0D, "tab": 0xFF09, "esc": 0xFF1B, "backspace": 0xFF08, "delete": 0xFFFF,
    "left": 0xFF51, "up": 0xFF52, "right": 0xFF53, "down": 0xFF54, "home": 0xFF50, "end": 0xFF57,
    "pgup": 0xFF55, "pgdn": 0xFF56, "spc": 0x20, "space": 0x20,
    "shift": 0xFFE1, "ctrl": 0xFFE3, "alt": 0xFFE9, "opt": 0xFFE9, "meta": 0xFFEB, "cmd": 0xFFEB, "super": 0xFFEB,
}
for _i in range(1, 13):
    KEYSYMS[f"f{_i}"] = 0xFFBE + _i - 1
SHIFTED = set('~!@#$%^&*()_+{}|:"<>?') | set("ABCDEFGHIJKLMNOPQRSTUVWXYZ")


class UnixTransport:
    def __init__(self, path):
        self.s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.s.connect(path)
        self.s.settimeout(30)

    def send(self, data):
        self.s.sendall(data)

    def recv(self, n):
        buf = bytearray()
        while len(buf) < n:
            chunk = self.s.recv(n - len(buf))
            if not chunk:
                raise ConnectionError("vnc socket closed")
            buf += chunk
        return bytes(buf)

    def close(self):
        self.s.close()


class PveWsTransport:
    """RFB over the Proxmox vncwebsocket endpoint (RFC6455 client, binary subprotocol)."""

    def __init__(self, api_host, node, vmid, auth_headers, verify=False, timeout=30):
        u = urllib.parse.urlparse(api_host)
        self.host = u.hostname
        self.port = u.port or 8006
        self.auth_headers = dict(auth_headers)
        ctx = ssl.create_default_context()
        if not verify:
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
        self.ctx = ctx
        self.base = f"{u.scheme}://{self.host}:{self.port}"
        # 1. ask Proxmox for a VNC proxy ticket (websocket mode)
        body = urllib.parse.urlencode({"websocket": 1}).encode()
        req = urllib.request.Request(f"{self.base}/api2/json/nodes/{node}/qemu/{vmid}/vncproxy", data=body, method="POST")
        for k, v in self.auth_headers.items():
            req.add_header(k, v)
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
            data = json.load(r)["data"]
        self.ticket = data["ticket"]
        vport = data["port"]
        # 2. websocket upgrade to the vncwebsocket endpoint
        q = urllib.parse.urlencode({"port": vport, "vncticket": self.ticket})
        path = f"/api2/json/nodes/{node}/qemu/{vmid}/vncwebsocket?{q}"
        raw = socket.create_connection((self.host, self.port), timeout=timeout)
        self.s = ctx.wrap_socket(raw, server_hostname=self.host)
        key = base64.b64encode(os.urandom(16)).decode()
        hdr = [f"GET {path} HTTP/1.1", f"Host: {self.host}:{self.port}", "Upgrade: websocket", "Connection: Upgrade",
               f"Sec-WebSocket-Key: {key}", "Sec-WebSocket-Version: 13", "Sec-WebSocket-Protocol: binary"]
        for k, v in self.auth_headers.items():
            hdr.append(f"{k}: {v}")
        self.s.sendall(("\r\n".join(hdr) + "\r\n\r\n").encode())
        resp = b""
        while b"\r\n\r\n" not in resp:
            chunk = self.s.recv(4096)
            if not chunk:
                raise ConnectionError("websocket upgrade: connection closed")
            resp += chunk
        head, _, rest = resp.partition(b"\r\n\r\n")
        status = head.split(b"\r\n", 1)[0]
        if b" 101 " not in status:
            raise ConnectionError(f"websocket upgrade failed: {status.decode(errors='replace')}")
        self.rbuf = bytearray(rest)   # any RFB bytes already received after the headers
        self.frame = bytearray()      # decoded payload not yet consumed

    def _raw_recv(self, n):
        while len(self.rbuf) < n:
            chunk = self.s.recv(65536)
            if not chunk:
                raise ConnectionError("websocket closed")
            self.rbuf += chunk
        out = bytes(self.rbuf[:n])
        del self.rbuf[:n]
        return out

    def _read_frame(self):
        b0, b1 = self._raw_recv(2)
        opcode = b0 & 0x0F
        masked = b1 & 0x80
        ln = b1 & 0x7F
        if ln == 126:
            ln = struct.unpack(">H", self._raw_recv(2))[0]
        elif ln == 127:
            ln = struct.unpack(">Q", self._raw_recv(8))[0]
        mask = self._raw_recv(4) if masked else None
        payload = self._raw_recv(ln)
        if mask:
            payload = bytes(c ^ mask[i % 4] for i, c in enumerate(payload))
        if opcode == 0x8:
            raise ConnectionError("websocket close frame")
        if opcode == 0x9:  # ping -> pong
            self._send_frame(0xA, payload)
            return b""
        if opcode in (0x0, 0x1, 0x2):
            return payload
        return b""

    def _send_frame(self, opcode, payload):
        mask = os.urandom(4)
        ln = len(payload)
        hdr = bytes([0x80 | opcode])
        if ln < 126:
            hdr += bytes([0x80 | ln])
        elif ln < 65536:
            hdr += bytes([0x80 | 126]) + struct.pack(">H", ln)
        else:
            hdr += bytes([0x80 | 127]) + struct.pack(">Q", ln)
        masked = bytes(c ^ mask[i % 4] for i, c in enumerate(payload))
        self.s.sendall(hdr + mask + masked)

    def send(self, data):
        self._send_frame(0x2, data)

    def recv(self, n):
        while len(self.frame) < n:
            self.frame += self._read_frame()
        out = bytes(self.frame[:n])
        del self.frame[:n]
        return out

    def close(self):
        try:
            self._send_frame(0x8, b"")
        except Exception:
            pass
        self.s.close()


class RFB:
    def __init__(self, transport, password=None):
        self.t = transport
        self.width = self.height = 0
        self.fb = None  # bytes, BGRX little-endian 32bpp, row-major
        self._handshake(password)

    # --- protocol -------------------------------------------------------
    def _handshake(self, password):
        ver = self.t.recv(12)
        if not ver.startswith(b"RFB "):
            raise ConnectionError(f"not an RFB server: {ver!r}")
        self.t.send(b"RFB 003.008\n")
        n = self.t.recv(1)[0]
        if n == 0:
            ln = struct.unpack(">I", self.t.recv(4))[0]
            raise ConnectionError("server refused: " + self.t.recv(ln).decode(errors="replace"))
        types = list(self.t.recv(n))
        if 2 in types:
            self.t.send(b"\x02")
            chal = self.t.recv(16)
            self.t.send(vnc_encrypt_challenge(password or "", chal))
        elif 1 in types:
            self.t.send(b"\x01")
        else:
            raise ConnectionError(f"unsupported VNC security types {types}")
        res = struct.unpack(">I", self.t.recv(4))[0]
        if res != 0:
            ln = struct.unpack(">I", self.t.recv(4))[0]
            raise ConnectionError("VNC auth failed: " + self.t.recv(ln).decode(errors="replace"))
        self.t.send(b"\x01")  # ClientInit: shared
        w, h = struct.unpack(">HH", self.t.recv(4))
        self.t.recv(16)  # server pixel format (we override it)
        ln = struct.unpack(">I", self.t.recv(4))[0]
        self.name = self.t.recv(ln).decode(errors="replace")
        self._resize(w, h)
        # SetPixelFormat: 32bpp, depth 24, little-endian, true colour, R<<16 G<<8 B
        pf = struct.pack(">BBBBHHHBBBxxx", 32, 24, 0, 1, 255, 255, 255, 16, 8, 0)
        self.t.send(b"\x00\x00\x00\x00" + pf)
        # SetEncodings: raw + DesktopSize
        self.t.send(struct.pack(">BxH", 2, 2) + struct.pack(">ii", 0, -223))

    def _resize(self, w, h):
        self.width, self.height = w, h
        self.fb = bytearray(w * h * 4)

    def _server_message(self, want_update=True):
        """Read one server message. Returns True if it was a FramebufferUpdate."""
        mt = self.t.recv(1)[0]
        if mt == 0:
            self.t.recv(1)
            nrects = struct.unpack(">H", self.t.recv(2))[0]
            for _ in range(nrects):
                x, y, w, h, enc = struct.unpack(">HHHHi", self.t.recv(12))
                if enc == 0:
                    data = self.t.recv(w * h * 4)
                    for row in range(h):
                        off = ((y + row) * self.width + x) * 4
                        self.fb[off:off + w * 4] = data[row * w * 4:(row + 1) * w * 4]
                elif enc == -223:
                    self._resize(w, h)
                else:
                    raise ConnectionError(f"unexpected encoding {enc}")
            return True
        if mt == 1:  # SetColourMapEntries
            self.t.recv(1)
            _, n = struct.unpack(">HH", self.t.recv(4))
            self.t.recv(n * 6)
        elif mt == 2:  # Bell
            pass
        elif mt == 3:  # ServerCutText
            self.t.recv(3)
            ln = struct.unpack(">I", self.t.recv(4))[0]
            self.t.recv(ln)
        else:
            raise ConnectionError(f"unknown server message {mt}")
        return False

    def refresh(self):
        """Request a full (non-incremental) framebuffer update and wait for it."""
        self.t.send(struct.pack(">BBHHHH", 3, 0, 0, 0, self.width, self.height))
        while not self._server_message():
            pass
        return self.fb

    # --- input ----------------------------------------------------------
    def key(self, keysym, down):
        self.t.send(struct.pack(">BBxxI", 4, 1 if down else 0, keysym))

    def press(self, name, hold=0.04):
        """Press a named key or key combo (e.g. 'ret', 'cmd-q', 'ctrl-c', 'shift-right')."""
        parts = name.split("-") if name != "-" else ["-"]
        syms = []
        for p in parts:
            if p in KEYSYMS:
                syms.append(KEYSYMS[p])
            elif len(p) == 1:
                syms.append(ord(p))
            else:
                raise ValueError(f"unknown key {p}")
        for s in syms:
            self.key(s, True)
            time.sleep(0.01)
        time.sleep(hold)
        for s in reversed(syms):
            self.key(s, False)
            time.sleep(0.01)

    def type_text(self, text, delay=0.025):
        """Type printable ASCII. Shift is held/released with generous gaps: the
        guest processes key events asynchronously and a shift release racing the
        next key turns '8' into '*'."""
        for ch in text:
            if ch == "\n":
                self.press("ret")
                time.sleep(0.05)
            elif ch == "\t":
                self.press("tab")
            else:
                shifted = ch in SHIFTED
                if shifted:
                    self.key(KEYSYMS["shift"], True)
                    time.sleep(0.02)
                self.key(ord(ch), True)
                time.sleep(0.012)
                self.key(ord(ch), False)
                if shifted:
                    time.sleep(0.02)
                    self.key(KEYSYMS["shift"], False)
                    time.sleep(0.02)
            time.sleep(delay)

    def pointer(self, x, y, mask=0):
        self.t.send(struct.pack(">BBHH", 5, mask, max(0, min(x, self.width - 1)), max(0, min(y, self.height - 1))))

    def click(self, x, y, count=1):
        self.pointer(x, y, 0)
        time.sleep(0.25)
        for _ in range(count):
            self.pointer(x, y, 1)
            time.sleep(0.08)
            self.pointer(x, y, 0)
            time.sleep(0.1)

    # --- pixels ---------------------------------------------------------
    def pixel(self, x, y):
        off = (y * self.width + x) * 4
        b, g, r = self.fb[off], self.fb[off + 1], self.fb[off + 2]
        return (r, g, b)

    def region_mean(self, x0, y0, x1, y1, step=2):
        n = 0
        rs = gs = bs = 0
        for y in range(y0, y1, step):
            base = y * self.width * 4
            for x in range(x0, x1, step):
                off = base + x * 4
                bs += self.fb[off]
                gs += self.fb[off + 1]
                rs += self.fb[off + 2]
                n += 1
        return (rs // n, gs // n, bs // n) if n else (0, 0, 0)

    def region_fraction(self, x0, y0, x1, y1, pred, step=2):
        """Fraction of sampled pixels in the box for which pred((r,g,b)) is true."""
        n = hit = 0
        for y in range(y0, y1, step):
            base = y * self.width * 4
            for x in range(x0, x1, step):
                off = base + x * 4
                if pred((self.fb[off + 2], self.fb[off + 1], self.fb[off])):
                    hit += 1
                n += 1
        return hit / n if n else 0.0

    def save_png(self, path):
        w, h = self.width, self.height
        raw = bytearray()
        fb = self.fb
        for y in range(h):
            raw.append(0)
            row = fb[y * w * 4:(y + 1) * w * 4]
            # BGRX -> RGB
            raw += bytes(v for i in range(0, len(row), 4) for v in (row[i + 2], row[i + 1], row[i]))

        def chunk(t, d):
            c = t + d
            return struct.pack(">I", len(d)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)
        png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
        png += chunk(b"IDAT", zlib.compress(bytes(raw), 6)) + chunk(b"IEND", b"")
        with open(path, "wb") as f:
            f.write(png)

    def close(self):
        self.t.close()


def pve_post(a, path, body=None, timeout=60):
    """POST to the Proxmox API using the driver's argparse namespace for host/auth."""
    hdr = {}
    if a.token_secret:
        hdr["Authorization"] = f"PVEAPIToken={a.token_user}={a.token_secret}"
    else:
        hdr["Cookie"] = f"PVEAuthCookie={a.ticket}"
        hdr["CSRFPreventionToken"] = a.csrf
    ctx = ssl.create_default_context()
    if a.insecure:
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    data = urllib.parse.urlencode(body or {}).encode()
    req = urllib.request.Request(a.api_host.rstrip("/") + "/api2/json" + path, data=data, method="POST")
    for k, v in hdr.items():
        req.add_header(k, v)
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
        return json.load(r)


def connect(spec, node=None, vmid=None, api_host=None, auth_headers=None, verify=False, password=None):
    """spec: 'unix:<path>' or 'pve'."""
    if spec.startswith("unix:"):
        return RFB(UnixTransport(spec[5:]), password=password)
    t = PveWsTransport(api_host, node, vmid, auth_headers, verify=verify)
    return RFB(t, password=t.ticket)


if __name__ == "__main__":
    # quick manual test: pvevnc.py unix:/var/run/qemu-server/108.vnc <password> shot out.png
    spec, pw, op = sys.argv[1], sys.argv[2], sys.argv[3]
    c = connect(spec, password=pw)
    c.refresh()
    if op == "shot":
        c.save_png(sys.argv[4])
        print(c.width, c.height, c.name)
    elif op == "type":
        c.type_text(sys.argv[4])
    elif op == "press":
        c.press(sys.argv[4])
    elif op == "click":
        c.click(int(sys.argv[4]), int(sys.argv[5]))
    c.close()
