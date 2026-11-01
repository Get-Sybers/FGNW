// Package scheduler manages the per-persona goroutines that drive activity on
// a cadence derived from each persona's pace and active window.
package scheduler

import (
	"math"
	"math/rand"
	"sync"
	"time"
)

// PaceProfile holds the base interval parameters for a named pace level.
type PaceProfile struct {
	// BaseMin / BaseMax are the min/max of a uniform draw for the inter-activity
	// interval at the "normal" activity rate.  Log-normal jitter is added on top.
	BaseMin time.Duration
	BaseMax time.Duration
}

var paceProfiles = map[string]PaceProfile{
	"obsessive": {BaseMin: 30 * time.Second, BaseMax: 90 * time.Second},
	"normal":    {BaseMin: 3 * time.Minute, BaseMax: 8 * time.Minute},
	"idle":      {BaseMin: 10 * time.Minute, BaseMax: 20 * time.Minute},
}

// NextDelay returns the duration to wait before the next activity for the
// given pace.  The interval is drawn from a uniform [min, max] base with a
// log-normal jitter factor (σ=0.3) applied — this produces a realistic
// distribution where most intervals cluster near the centre but occasional
// long pauses occur.
func NextDelay(pace string) time.Duration {
	prof, ok := paceProfiles[pace]
	if !ok {
		prof = paceProfiles["normal"]
	}
	rngMu.Lock()
	base := prof.BaseMin + time.Duration(rng.Int63n(int64(prof.BaseMax-prof.BaseMin)))
	rngMu.Unlock()

	// Log-normal jitter: multiply base by e^(sigma * N(0,1))
	const sigma = 0.3
	rngMu.Lock()
	z := rng.NormFloat64()
	rngMu.Unlock()
	factor := math.Exp(sigma * z)
	return time.Duration(float64(base) * factor)
}

// LunchIdleDuration returns a duration appropriate for a "away at lunch" lock
// cycle — between 25 and 65 minutes, jittered.
func LunchIdleDuration() time.Duration {
	rngMu.Lock()
	defer rngMu.Unlock()
	return 25*time.Minute + time.Duration(rng.Int63n(int64(40*time.Minute)))
}

// ShortBreakDuration is 3–10 minutes — a quick bio break or coffee run.
func ShortBreakDuration() time.Duration {
	rngMu.Lock()
	defer rngMu.Unlock()
	return 3*time.Minute + time.Duration(rng.Int63n(int64(7*time.Minute)))
}

// NightTrickleDelay returns a much longer delay for after-hours activity —
// 20–50 minutes between events, simulating "person still at their desk but
// mostly idle."
func NightTrickleDelay() time.Duration {
	rngMu.Lock()
	defer rngMu.Unlock()
	return 20*time.Minute + time.Duration(rng.Int63n(int64(30*time.Minute)))
}

// IsLunchWindow returns true if t is within a ±15-minute window around local
// noon — used to decide whether to run a lunch lock-cycle.
func IsLunchWindow(t time.Time) bool {
	h, m, _ := t.Clock()
	mins := h*60 + m
	return mins >= 11*60+45 && mins <= 13*60+15
}

// --- package-level RNG (seeded once) ----------------------------------------

var (
	rngMu sync.Mutex
	rng   = rand.New(rand.NewSource(time.Now().UnixNano()))
)
