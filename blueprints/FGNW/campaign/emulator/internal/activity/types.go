// Package activity defines the activity types fgnw-emulator can inject into a
// VM, and the per-persona weighting that chooses between them.
package activity

// Kind identifies one category of emulated user activity.
type Kind string

const (
	// KindLock injects Win+L to lock the workstation (4800 on the DC).
	KindLock Kind = "lock"

	// KindUnlock types the persona's password to unlock the locked screen
	// (4801 on the DC, plus the Kerberos TGT reuse).
	KindUnlock Kind = "unlock"

	// KindLogoff sends a graceful logoff (4634/4647).
	KindLogoff Kind = "logoff"

	// KindType injects a short typed phrase into whatever window has focus —
	// simulates the user working in a document or composing an email in the
	// already-running Office apps (driven by GHOSTS handlers).
	KindType Kind = "type"

	// KindOpenFile uses the Guest Agent to launch a document from the persona's
	// decoy share via "explorer.exe <UNC path>" — lands a CIFS type-3 logon
	// on the file server attributed to the persona and creates a real WINWORD/
	// EXCEL process tree.
	KindOpenFile Kind = "open_file"

	// KindIdleJitter inserts a short random idle (mouse wiggle) — produces
	// the "user present but not active" pattern that prevents screensaver/
	// auto-lock from firing at an unrealistic fixed interval.
	KindIdleJitter Kind = "idle_jitter"

	// KindMouseMove wiggles the mouse slightly without clicking anything.
	KindMouseMove Kind = "mouse_move"
)

// Weight maps an activity Kind to a relative probability weight.
type Weight struct {
	Kind   Kind
	Weight int
}

// PaceWeights returns a weighted slice of activity kinds tuned for the
// persona's pace setting.  The scheduler draws from this slice proportionally.
func PaceWeights(pace string) []Weight {
	switch pace {
	case "obsessive":
		return []Weight{
			{KindType, 40},
			{KindOpenFile, 20},
			{KindIdleJitter, 15},
			{KindMouseMove, 10},
			{KindLock, 5},
			{KindLogoff, 2},
		}
	case "idle":
		return []Weight{
			{KindIdleJitter, 50},
			{KindMouseMove, 30},
			{KindType, 10},
			{KindOpenFile, 5},
			{KindLock, 3},
			{KindLogoff, 1},
		}
	default: // normal
		return []Weight{
			{KindType, 30},
			{KindIdleJitter, 25},
			{KindOpenFile, 20},
			{KindMouseMove, 15},
			{KindLock, 7},
			{KindLogoff, 3},
		}
	}
}

// Sample returns a random Kind from a weighted slice.
// The weights do not need to sum to any particular value.
func Sample(weights []Weight) Kind {
	total := 0
	for _, w := range weights {
		total += w.Weight
	}
	if total == 0 {
		return KindIdleJitter
	}
	// Use a simple linear scan; the slice is short.
	n := randIntn(total)
	for _, w := range weights {
		n -= w.Weight
		if n < 0 {
			return w.Kind
		}
	}
	return weights[len(weights)-1].Kind
}
