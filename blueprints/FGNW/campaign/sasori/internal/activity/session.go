package activity

import (
	"fmt"
	"time"

	"github.com/get-sybers/sasori/internal/proxmox"
)

// SessionController runs the lifecycle actions (lock, unlock, logoff) for a
// single VM.  It holds the persona's domain credentials so it can type the
// password during unlock without the caller needing to know them.
type SessionController struct {
	pve      *proxmox.Client
	vmid     int
	domain   string
	sam      string
	password string
	dryRun   bool
}

// NewSessionController creates a SessionController.
func NewSessionController(pve *proxmox.Client, vmid int, domain, sam, password string, dryRun bool) *SessionController {
	return &SessionController{
		pve: pve, vmid: vmid,
		domain: domain, sam: sam, password: password,
		dryRun: dryRun,
	}
}

// Lock locks the workstation with Win+L (generates EventID 4800 on the DC).
func (s *SessionController) Lock() error {
	if s.dryRun {
		logDryRun("lock", s.vmid)
		return nil
	}
	return s.pve.SendKeyCombo(s.vmid, "meta_l", "l")
}

// Unlock types the persona's password on the lock screen and presses Enter.
// Produces EventID 4801 (workstation unlocked) + a Kerberos service-ticket
// reuse event on the DC attributed to the persona.
//
// The password is typed at a realistic cadence — the lock screen is just a
// text field, so this looks identical to a human typing their password.
func (s *SessionController) Unlock(wpm int) error {
	if s.dryRun {
		logDryRun("unlock", s.vmid)
		return nil
	}
	// Brief wait for the lock screen to fully render.
	time.Sleep(800 * time.Millisecond)

	delayMs := wpmToDelayMs(wpm)
	if err := s.pve.TypeString(s.vmid, s.password, delayMs, 0.0); err != nil {
		return fmt.Errorf("unlock type password: %w", err)
	}
	time.Sleep(logNormalMillis(200))
	return s.pve.SendKey(s.vmid, "ret")
}

// Logoff sends a graceful logoff via the Guest Agent (rundll32 ExitWindowsEx).
// Produces EventID 4634/4647 on the DC.
func (s *SessionController) Logoff() error {
	if s.dryRun {
		logDryRun("logoff", s.vmid)
		return nil
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
// moving the visible cursor in any meaningful direction — identical to a user
// slightly shifting their hand on the mouse.
func (s *SessionController) MouseJitter() error {
	if s.dryRun {
		logDryRun("mouse_jitter", s.vmid)
		return nil
	}
	// HMP mouse_move dx dy — relative movement in pixels.
	moves := []string{"mouse_move 3 0", "mouse_move 0 3", "mouse_move -3 0", "mouse_move 0 -3"}
	for _, m := range moves {
		if err := s.pve.SendKey(s.vmid, m); err != nil {
			// mouse_move is best-effort — don't abort on failure.
			_ = err
		}
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

func logNormalMillis(meanMs float64) time.Duration {
	// Re-uses the log-normal from keycodes.go via the proxmox package; here we
	// just want a simple in-package implementation without the cross-package call.
	return time.Duration(meanMs) * time.Millisecond
}

func logDryRun(action string, vmid int) {
	fmt.Printf("[dry-run] %s → vmid %d\n", action, vmid)
}
