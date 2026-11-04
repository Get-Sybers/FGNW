#!/usr/bin/env python3
"""Unattended macOS install driver for the Ludus macOS template (Proxmox + OpenCore).

Drives the VM's console over VNC (Proxmox API websocket - no root, no `qm`),
recognising screens by pixel probes and typing into the Recovery Terminal.

Stage "install" (VM freshly created, booted into macOS Recovery from the
BaseSystem disk):
  1. wait for the Recovery chooser, open Utilities > Terminal
  2. type a one-liner: find the blank target disk, erase it as APFS
     "Macintosh HD", print a green/red marker row, then run the full
     installer's `startosinstall --agreetolicense --nointeraction`
  3. wait for the installer's reboots and for the installed OS to reach a
     bright screen (Setup Assistant) - the install is complete

Stage "inject" (install complete, Setup Assistant on screen):
  4. reset the VM, pick "macOS Base System" in the OpenCore picker (last entry)
  5. in the Recovery Terminal, mount the Data volume and write the first-boot
     LaunchDaemon + script (typed as base64), touch .AppleSetupDone, reboot
  6. the first boot runs the daemon: creates the admin user, enables SSH

Every state change is logged (stdout) with a PNG in --log-dir for post-mortem.
"""
import argparse
import hashlib
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pvevnc  # noqa: E402

GREEN = ("\\e[42m%80s\\e[0m\\n", "")
# Recovery Terminal window geometry (Monterey/Ventura at 1280x800).
TERM_BOX = (45, 90, 600, 420)
UTILITIES_MENU = (242, 11)
TERMINAL_ITEM = (245, 63)


def ts():
    return time.strftime("%H:%M:%S")


class Driver:
    def __init__(self, args):
        self.a = args
        self.log_dir = args.log_dir
        os.makedirs(self.log_dir, exist_ok=True)
        self.shot_n = 0
        self.c = None
        self.connect()

    # --- plumbing -------------------------------------------------------
    def connect(self):
        a = self.a
        last = None
        for _ in range(30):
            try:
                if a.unix_socket:
                    self.c = pvevnc.connect(f"unix:{a.unix_socket}", password=a.vnc_password)
                else:
                    hdr = {}
                    if a.token_secret:
                        hdr["Authorization"] = f"PVEAPIToken={a.token_user}={a.token_secret}"
                    else:
                        hdr["Cookie"] = f"PVEAuthCookie={a.ticket}"
                        hdr["CSRFPreventionToken"] = a.csrf
                    self.c = pvevnc.connect("pve", node=a.node, vmid=a.vmid, api_host=a.api_host,
                                            auth_headers=hdr, verify=not a.insecure)
                return
            except Exception as e:  # VM may be rebooting / proxy not ready
                last = e
                time.sleep(5)
        raise SystemExit(f"could not open the VNC console: {last}")

    def log(self, msg):
        print(f"[{ts()}] {msg}", flush=True)

    def shot(self, tag):
        self.shot_n += 1
        p = os.path.join(self.log_dir, f"{self.shot_n:03d}_{tag}.png")
        try:
            self.c.save_png(p)
        except Exception as e:
            self.log(f"screenshot failed: {e}")
        return p

    def frame(self):
        """Fetch a fresh framebuffer, reconnecting if the VNC session dropped (reboot)."""
        for _ in range(3):
            try:
                self.c.refresh()
                return self.c
            except Exception as e:
                self.log(f"console dropped ({e}); reconnecting")
                try:
                    self.c.close()
                except Exception:
                    pass
                time.sleep(3)
                self.connect()
        raise SystemExit("console unusable")

    def wait_for(self, name, pred, timeout, interval=1.0, stable=1):
        """Poll until pred(frame) holds for `stable` consecutive samples."""
        t0 = time.time()
        ok = 0
        while time.time() - t0 < timeout:
            f = self.frame()
            if pred(f):
                ok += 1
                if ok >= stable:
                    self.log(f"state: {name} (after {int(time.time() - t0)}s) -> {self.shot(name)}")
                    return True
            else:
                ok = 0
            time.sleep(interval)
        self.log(f"TIMEOUT waiting for {name} ({timeout}s) -> {self.shot('timeout_' + name)}")
        return False

    # --- screen probes --------------------------------------------------
    @staticmethod
    def mean_all(f):
        return sum(f.region_mean(0, 0, f.width, f.height, 8)) // 3

    @staticmethod
    def menubar_ok(f):
        m = f.region_mean(300, 2, 1000, 20)
        r, g, b = f.pixel(25, 11)
        return all(24 <= v <= 48 for v in m) and min(r, g, b) > 180

    def is_recovery(self, f):
        """Recovery chooser (or any Recovery app): macOS menu bar, no Terminal traffic lights."""
        return self.menubar_ok(f) and not self.is_terminal(f)

    def is_terminal(self, f):
        if not self.menubar_ok(f):
            return False
        r, g, b = f.pixel(54, 70)
        r2, g2, b2 = f.pixel(94, 70)
        return r > 180 and g < 140 and g2 > 150 and r2 < 110

    @staticmethod
    def marker_row(f, color):
        x0, y0, x1, y1 = TERM_BOX
        if color == "green":
            pred = lambda p: p[0] < 100 and p[1] > 140 and p[2] < 100  # noqa: E731
        else:
            pred = lambda p: p[0] > 110 and p[1] < 70 and p[2] < 70  # noqa: E731
        for y in range(y0, y1, 2):
            if f.region_fraction(x0, y, x1, y + 1, pred, step=4) > 0.85:
                return True
        return False

    def is_black(self, f):
        return self.mean_all(f) < 4

    def is_bright(self, f):
        return self.mean_all(f) > 90

    @staticmethod
    def picker_icons(f):
        xs = [x for x in range(0, f.width, 2) if max(f.pixel(x, 380)) > 90]
        cl = []
        for x in xs:
            if cl and x - cl[-1][1] <= 6:
                cl[-1][1] = x
            else:
                cl.append([x, x])
        return [c for c in cl if c[1] - c[0] >= 40]

    @staticmethod
    def picker_highlight(f):
        xs = [x for x in range(0, f.width, 2) if all(118 <= v <= 138 for v in f.pixel(x, 322))]
        cl = []
        for x in xs:
            if cl and x - cl[-1][1] <= 6:
                cl[-1][1] = x
            else:
                cl.append([x, x])
        return [c for c in cl if c[1] - c[0] >= 40]

    def is_picker(self, f):
        if self.mean_all(f) > 25:
            return False
        icons = self.picker_icons(f)
        if not icons:
            return False
        # power / reset buttons under the entries and the OpenCore release label
        # bottom-right; the Proxmox/OVMF splash and the Apple boot screen have neither.
        buttons = f.region_fraction(575, 718, 705, 760, lambda p: min(p) > 150, step=2)
        rel = f.region_fraction(1100, 768, 1260, 786, lambda p: min(p) > 150, step=1)
        return buttons > 0.02 and rel > 0.02

    # Column projection (bright pixels per column, rows 462-479) of the OpenCanopy
    # label "macOS Base System" at 1280x800 - identical across boots/VMs.
    BASE_SYSTEM_LABEL = [5, 6, 1, 2, 6, 1, 2, 5, 2, 6, 4, 6, 5, 1, 3, 6, 2, 4, 2, 4, 6, 3, 3, 3, 3, 6, 2, 0, 6, 3, 5, 3, 6,
                         0, 0, 0, 0, 0, 8, 5, 5, 6, 7, 0, 2, 6, 4, 6, 5, 1, 2, 5, 4, 5, 3, 2, 6, 4, 5, 5, 0, 0, 0, 0, 0, 6,
                         3, 5, 3, 6, 0, 3, 5, 4, 4, 2, 2, 5, 4, 5, 3, 2, 7, 2, 2, 6, 4, 5, 5, 0, 5, 6, 1, 2, 6, 1, 2, 5]

    @staticmethod
    def picker_label(f, icon):
        cx = (icon[0] + icon[1]) // 2
        cols = [sum(1 for y in range(462, 480) if min(f.pixel(x, y)) > 120) for x in range(cx - 90, cx + 90)]
        nz = [i for i, v in enumerate(cols) if v]
        return cols[nz[0]:nz[-1] + 1] if nz else []

    def label_is_base_system(self, f, icon):
        lab = self.picker_label(f, icon)
        ref = self.BASE_SYSTEM_LABEL
        if abs(len(lab) - len(ref)) > 1:
            return False
        n = min(len(lab), len(ref))
        return sum(abs(a - b) for a, b in zip(lab[:n], ref[:n])) <= 20

    # --- actions --------------------------------------------------------
    def open_terminal(self):
        for attempt in range(4):
            self.c.click(*UTILITIES_MENU)
            time.sleep(1.0)
            self.frame()
            self.shot("utilities_menu")
            self.c.click(*TERMINAL_ITEM)
            if self.wait_for("terminal", self.is_terminal, 20, interval=1.0):
                time.sleep(1.5)
                return True
            self.c.press("esc")
            time.sleep(1)
        return False

    def type_line(self, text, delay=0.02):
        self.c.type_text(text + "\n", delay=delay)

    def type_file(self, dest, data: bytes):
        """Type a text file into the Recovery shell via a quoted heredoc (Recovery
        has no base64/python), then verify its md5 with the marker rows."""
        text = data.decode("ascii")
        if any(ord(ch) > 126 or (ord(ch) < 32 and ch not in "\n") for ch in text):
            raise SystemExit(f"{dest}: only printable ASCII can be typed through the console")
        if not text.endswith("\n"):
            raise SystemExit(f"{dest}: the file must end with a newline (the heredoc adds one after the last line)")
        self.type_line(f"cat > '{dest}' <<'LUDUSEOF'")
        for line in text[:-1].split("\n"):
            self.type_line(line)
        self.type_line("LUDUSEOF")
        digest = hashlib.md5(data).hexdigest()
        ok = 'printf "' + GREEN[0] + '" ""'
        ko = ok.replace("42m", "41m")
        self.type_line(f"[ \"$(md5 -q '{dest}')\" = {digest} ] && {ok} || {ko}")
        if not self.wait_marker(120, f"typed {os.path.basename(dest)}"):
            raise SystemExit(f"{dest} did not arrive intact in the guest (see screenshot)")

    def wait_marker(self, timeout, what):
        """Wait for a green (True) or red (False) marker row in the Terminal; None on timeout."""
        t0 = time.time()
        while time.time() - t0 < timeout:
            f = self.frame()
            if self.marker_row(f, "green"):
                self.log(f"{what}: ok -> {self.shot('ok')}")
                self.type_line("printf '\\e[2J\\e[H'")  # clear so the next marker is unambiguous
                time.sleep(1)
                return True
            if self.marker_row(f, "red"):
                self.log(f"{what}: FAILED -> {self.shot('failed')}")
                return False
            time.sleep(2)
        self.log(f"{what}: no marker within {timeout}s -> {self.shot('timeout')}")
        return None

    # --- stages ---------------------------------------------------------
    def stage_install(self):
        a = self.a
        if not self.wait_for("recovery", self.is_recovery, a.boot_timeout, interval=2.0, stable=2):
            raise SystemExit("Recovery never appeared (is the BaseSystem disk attached and OpenCore booting it?)")
        time.sleep(3)
        if not self.open_terminal():
            raise SystemExit("could not open Terminal from the Utilities menu")
        ok = 'printf "' + GREEN[0] + '" ""'
        ko = ok.replace("42m", "41m")
        # Find the blank target disk: a physical disk with no partitions and > 20 GB.
        find = ("T=; for d in $(diskutil list physical | awk '/^\\/dev\\/disk/{print $1}'); do "
                "n=$(diskutil list $d | grep -c -E '^ +[1-9][0-9]*:'); "
                "s=$(diskutil info $d | awk -F'[()]' '/Disk Size/{print $2}' | awk '{print $1}'); "
                "if [ \"$n\" = 0 ] && [ \"${s:-0}\" -gt 20000000000 ]; then T=$d; fi; done; echo target=$T")
        self.type_line(find)
        erase = (f"[ -n \"$T\" ] && diskutil eraseDisk APFS 'Macintosh HD' GPT $T && "
                 "A=$(ls -d '/Volumes/Install macOS '*/'Install macOS '*.app | head -1) && [ -n \"$A\" ] && "
                 f"{ok} || {ko}")
        self.type_line(erase)
        if not self.wait_marker(240, "target disk erased as APFS 'Macintosh HD'"):
            raise SystemExit("target disk erase / installer lookup failed (see screenshot)")
        inst = ("\"$A/Contents/Resources/startosinstall\" --volume '/Volumes/Macintosh HD' "
                f"--agreetolicense --nointeraction --forcequitapps; {ko}")
        self.type_line(inst)
        self.log("startosinstall launched; waiting for the installer to reboot the VM")
        # Phase 1 copies the installer payload (minutes), then reboots: the screen goes black.
        t0 = time.time()
        while time.time() - t0 < a.phase1_timeout:
            f = self.frame()
            if self.is_black(f):
                self.log(f"VM rebooted into the installer phase (after {int(time.time() - t0)}s)")
                break
            if self.marker_row(f, "red"):
                self.shot("startosinstall_failed")
                raise SystemExit("startosinstall returned an error (see screenshot)")
            if int(time.time() - t0) % 120 == 0:
                self.shot("phase1")
            time.sleep(5)
        else:
            self.shot("phase1_timeout")
            raise SystemExit("installer phase 1 did not reboot in time")
        # Phase 2 (+3): Apple logo progress bars, one or more reboots, then the
        # installed OS reaches Setup Assistant (a bright screen).
        if not self.wait_for("install_complete", self.is_bright, a.install_timeout, interval=15.0, stable=3):
            raise SystemExit("the installed OS never reached Setup Assistant")
        self.log("macOS install complete")

    def select_base_system(self):
        """In the OpenCore picker, move the highlight onto "macOS Base System" and boot it."""
        # The picker auto-boots its default after Timeout (2 s in the LongQT ISO) and
        # only a non-modifier key halts the countdown: press an arrow at once and
        # re-read the highlight afterwards.
        self.c.press("left")
        time.sleep(0.4)
        for _ in range(8):
            f = self.frame()
            icons = self.picker_icons(f)
            hl = self.picker_highlight(f)
            if not icons:
                time.sleep(0.5)
                continue
            idx = -1
            if hl:
                hx = (hl[0][0] + hl[0][1]) // 2
                for i, c in enumerate(icons):
                    if c[0] - 12 <= hx <= c[1] + 12:
                        idx = i
            target = [i for i, c in enumerate(icons) if self.label_is_base_system(f, c)]
            self.log(f"picker: {len(icons)} entries, highlighted {idx}, base system at {target}")
            if not target:
                time.sleep(0.5)
                continue
            if idx == target[0]:
                self.shot("picker_selected")
                self.c.press("ret")
                return True
            if idx < 0:
                self.c.press("left")
            else:
                key = "right" if target[0] > idx else "left"
                for _ in range(abs(target[0] - idx)):
                    self.c.press(key)
                    time.sleep(0.3)
            time.sleep(0.6)
        return False

    def stage_inject(self):
        a = self.a
        for attempt in range(1, 4):
            self.log(f"resetting the VM to boot the OpenCore picker (attempt {attempt})")
            if a.reset_cmd:
                os.system(a.reset_cmd)
            else:
                pvevnc.pve_post(a, f"/nodes/{a.node}/qemu/{a.vmid}/status/reset")
            if not self.wait_for("picker", self.is_picker, 180, interval=0.2):
                raise SystemExit("OpenCore picker not seen after reset")
            if not self.select_base_system():
                raise SystemExit("could not select the macOS Base System entry in the picker")
            # Recovery takes ~15 s from the picker; a bright screen means the countdown
            # won and the installed OS booted instead - reset and try again.
            if self.wait_for("recovery2", lambda f: self.is_recovery(f) or self.is_bright(f), a.boot_timeout,
                             interval=2.0, stable=2) and self.is_recovery(self.frame()):
                break
            self.log("the installed OS booted instead of Recovery; retrying")
        else:
            raise SystemExit("could not boot macOS Base System from the picker")
        time.sleep(3)
        if not self.open_terminal():
            raise SystemExit("could not open Terminal (second pass)")
        ok = 'printf "' + GREEN[0] + '" ""'
        ko = ok.replace("42m", "41m")
        script = open(a.firstboot_script, "rb").read()
        script = script.replace(b"__LUDUS_USER__", a.username.encode()).replace(b"__LUDUS_PASS__", a.password.encode())
        plist = open(a.launchd_plist, "rb").read()
        self.type_line("diskutil mount 'Macintosh HD - Data'; D=/Volumes/'Macintosh HD - Data'; ls -d \"$D\" && "
                       f"mkdir -p \"$D/Library/LaunchDaemons\" \"$D/usr/local/bin\" \"$D/private/var/db\" && {ok} || {ko}")
        if not self.wait_marker(60, "Data volume mounted"):
            raise SystemExit("the installed system's Data volume was not found in Recovery")
        self.type_file("/tmp/first-boot.sh", script)
        self.type_file("/tmp/com.ludus.firstboot.plist", plist)
        fin = ("cp /tmp/first-boot.sh \"$D/usr/local/bin/ludus-first-boot.sh\" && "
               "cp /tmp/com.ludus.firstboot.plist \"$D/Library/LaunchDaemons/com.ludus.firstboot.plist\" && "
               "chmod 755 \"$D/usr/local/bin/ludus-first-boot.sh\" && chmod 644 \"$D/Library/LaunchDaemons/com.ludus.firstboot.plist\" && "
               "chown 0:0 \"$D/usr/local/bin/ludus-first-boot.sh\" \"$D/Library/LaunchDaemons/com.ludus.firstboot.plist\" && "
               f"touch \"$D/private/var/db/.AppleSetupDone\" && sync && {ok} || {ko}")
        self.type_line(fin)
        if not self.wait_marker(120, "first-boot LaunchDaemon installed on the Data volume"):
            raise SystemExit("first-boot injection failed (see screenshot)")
        self.type_line("reboot")
        self.log("rebooting into the installed macOS; the first-boot daemon will create the user and enable SSH")
        time.sleep(5)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--stage", choices=["install", "inject", "all"], default="all")
    p.add_argument("--api-host")
    p.add_argument("--node")
    p.add_argument("--vmid")
    p.add_argument("--token-user")
    p.add_argument("--token-secret", default=os.environ.get("PVE_TOKEN_SECRET", ""))
    p.add_argument("--ticket", default=os.environ.get("PVE_TICKET", ""))
    p.add_argument("--csrf", default=os.environ.get("PVE_CSRF", ""))
    p.add_argument("--insecure", action="store_true")
    p.add_argument("--unix-socket", help="dev: connect to /var/run/qemu-server/<id>.vnc directly (root)")
    p.add_argument("--vnc-password", default="")
    p.add_argument("--reset-cmd", default="", help="dev: shell command that resets the VM (e.g. 'qm reset 108')")
    p.add_argument("--log-dir", required=True)
    p.add_argument("--username", default="localuser")
    p.add_argument("--password", default="password")
    p.add_argument("--firstboot-script")
    p.add_argument("--launchd-plist")
    p.add_argument("--boot-timeout", type=int, default=600)
    p.add_argument("--phase1-timeout", type=int, default=5400)
    p.add_argument("--install-timeout", type=int, default=14400)
    a = p.parse_args()
    if a.stage in ("inject", "all") and not (a.firstboot_script and a.launchd_plist):
        p.error("--firstboot-script and --launchd-plist are required for the inject stage")
    d = Driver(a)
    if a.stage in ("install", "all"):
        d.stage_install()
    if a.stage in ("inject", "all"):
        if a.stage == "all":
            time.sleep(20)
        d.stage_inject()
    d.log("driver finished")


if __name__ == "__main__":
    main()
