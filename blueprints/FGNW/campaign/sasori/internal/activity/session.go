package activity

import (
	"fmt"
	"math"
	"time"

	"github.com/get-sybers/sasori/internal/proxmox"
)

// SessionController runs the lifecycle actions (lock, unlock, logoff) for a
// single VM.  It holds the persona's domain credentials so it can type the
// password during unlock without the caller needing to know them.
type SessionController struct {
	pve      *proxmox.Client
	vmid     int
	guestOS  string // "windows" (default) or "macos"
	domain   string
	sam      string
	password string
	dryRun   bool
}

// NewSessionController creates a SessionController.
// guestOS is "windows" (empty string also defaults to Windows) or "macos".
func NewSessionController(pve *proxmox.Client, vmid int, domain, sam, password, guestOS string, dryRun bool) *SessionController {
	if guestOS == "" {
		guestOS = "windows"
	}
	return &SessionController{
		pve: pve, vmid: vmid,
		guestOS:  guestOS,
		domain:   domain,
		sam:      sam,
		password: password,
		dryRun:   dryRun,
	}
}

// Lock locks the workstation.
//
// Windows: Win+L — generates EventID 4800 on the DC.
// macOS:   Cmd+Ctrl+Q — locks the screen on macOS 10.13+.
func (s *SessionController) Lock() error {
	if s.dryRun {
		logDryRun("lock", s.vmid)
		return nil
	}
	if s.guestOS == "macos" {
		return s.pve.SendKeyCombo(s.vmid, "meta_l", "ctrl", "q")
	}
	return s.pve.SendKeyCombo(s.vmid, "meta_l", "l")
}

// Unlock types the persona's password on the lock screen and presses Enter.
//
// Windows: produces EventID 4801 (workstation unlocked) + Kerberos TGT reuse.
// macOS:   same keystroke injection — lock screen accepts typed password.
func (s *SessionController) Unlock(wpm int) error {
	if s.dryRun {
		logDryRun("unlock", s.vmid)
		return nil
	}
	// Brief wait for the lock screen to fully render.
	time.Sleep(logNormalMillis(800))
	delayMs := wpmToDelayMs(wpm)
	if err := s.pve.TypeString(s.vmid, s.password, delayMs, 0.0); err != nil {
		return fmt.Errorf("unlock type password: %w", err)
	}
	time.Sleep(logNormalMillis(200))
	return s.pve.SendKey(s.vmid, "ret")
}

// Logoff sends a graceful logoff via the Guest Agent.
//
// Windows: rundll32 ExitWindowsEx — produces EventID 4634/4647 on the DC.
// macOS:   osascript tell System Events to log out.
func (s *SessionController) Logoff() error {
	if s.dryRun {
		logDryRun("logoff", s.vmid)
		return nil
	}
	if s.guestOS == "macos" {
		_, err := s.pve.AgentExec(s.vmid,
			"/usr/bin/osascript",
			[]string{"-e", `tell application "System Events" to log out`},
			15*time.Second)
		return err
	}
	_, err := s.pve.AgentExec(s.vmid,
		`C:\Windows\System32\rundll32.exe`,
		[]string{"user32.dll,ExitWindowsEx", "0", "0"},
		15*time.Second)
	return err
}

// LockUnlockCycle locks the workstation, waits idleFor, then unlocks.
// This is the most common real-user pattern (away at lunch / short break).
func (s *SessionController) LockUnlockCycle(idleFor time.Duration, wpm int) error {
	if err := s.Lock(); err != nil {
		return fmt.Errorf("lock: %w", err)
	}
	time.Sleep(idleFor)
	return s.Unlock(wpm)
}

// MouseJitter sends four tiny relative mouse moves that cancel each other out
// (net zero displacement).  This resets any screensaver/auto-lock timer without
// moving the visible cursor in any meaningful direction.
func (s *SessionController) MouseJitter() error {
	if s.dryRun {
		logDryRun("mouse_jitter", s.vmid)
		return nil
	}
	// Four moves that sum to zero: right, down, left, up.
	moves := [][2]int{{3, 0}, {0, 3}, {-3, 0}, {0, -3}}
	for _, m := range moves {
		// Best-effort — don't abort on mouse_move failure.
		_ = s.pve.MouseMove(s.vmid, m[0], m[1])
		time.Sleep(logNormalMillis(120))
	}
	return nil
}

// --- helpers ----------------------------------------------------------------

// wpmToDelayMs converts a words-per-minute typing speed to an average
// inter-keystroke delay in milliseconds (5 chars/word assumed).
func wpmToDelayMs(wpm int) float64 {
	if wpm <= 0 {
		wpm = 60
	}
	charsPerMin := float64(wpm) * 5.0
	return 60000.0 / charsPerMin
}

// logNormalMillis returns a duration drawn from a log-normal distribution
// with the given mean in milliseconds and σ=0.4 in log-space — realistic
// human reaction-time distribution with an occasional long pause.
func logNormalMillis(meanMs float64) time.Duration {
	const sigma = 0.4
	rngMu.Lock()
	z := rngSrc.NormFloat64()
	rngMu.Unlock()
	ms := meanMs * math.Exp(sigma*z)
	if ms < 20 {
		ms = 20
	}
	return time.Duration(ms) * time.Millisecond
}

func logDryRun(action string, vmid int) {
	fmt.Printf("[dry-run] %s → vmid %d\n", action, vmid)
}
