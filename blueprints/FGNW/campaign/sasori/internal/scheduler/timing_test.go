package scheduler

import (
	"testing"
	"time"
)

func makeTime(h, m int) time.Time {
	return time.Date(2024, 1, 1, h, m, 0, 0, time.UTC)
}

func TestIsLunchWindow(t *testing.T) {
	cases := []struct {
		h, m int
		want bool
	}{
		{11, 44, false}, // just before
		{11, 45, true},  // lower bound
		{12, 0, true},   // noon
		{13, 15, true},  // upper bound
		{13, 16, false}, // just after
	}
	for _, tc := range cases {
		got := IsLunchWindow(makeTime(tc.h, tc.m))
		if got != tc.want {
			t.Errorf("IsLunchWindow(%02d:%02d) = %v, want %v", tc.h, tc.m, got, tc.want)
		}
	}
}

func TestIsShortBreakAMWindow(t *testing.T) {
	cases := []struct {
		h, m int
		want bool
	}{
		{10, 14, false},
		{10, 15, true},
		{10, 30, true},
		{10, 45, true},
		{10, 46, false},
	}
	for _, tc := range cases {
		got := IsShortBreakAMWindow(makeTime(tc.h, tc.m))
		if got != tc.want {
			t.Errorf("IsShortBreakAMWindow(%02d:%02d) = %v, want %v", tc.h, tc.m, got, tc.want)
		}
	}
}

func TestIsShortBreakPMWindow(t *testing.T) {
	cases := []struct {
		h, m int
		want bool
	}{
		{14, 29, false},
		{14, 30, true},
		{15, 0, true},
		{15, 15, true},
		{15, 16, false},
	}
	for _, tc := range cases {
		got := IsShortBreakPMWindow(makeTime(tc.h, tc.m))
		if got != tc.want {
			t.Errorf("IsShortBreakPMWindow(%02d:%02d) = %v, want %v", tc.h, tc.m, got, tc.want)
		}
	}
}

func TestNextDelay_KnownPaces(t *testing.T) {
	for _, pace := range []string{"obsessive", "normal", "idle", "unknown"} {
		d := NextDelay(pace)
		if d <= 0 {
			t.Errorf("NextDelay(%q) = %v, want > 0", pace, d)
		}
		if d > 120*time.Minute {
			t.Errorf("NextDelay(%q) = %v, unexpectedly long", pace, d)
		}
	}
}

func TestLunchIdleDuration_InRange(t *testing.T) {
	for i := 0; i < 50; i++ {
		d := LunchIdleDuration()
		if d < 25*time.Minute || d > 65*time.Minute {
			t.Errorf("LunchIdleDuration() = %v, want 25–65 min", d)
		}
	}
}

func TestShortBreakDuration_InRange(t *testing.T) {
	for i := 0; i < 50; i++ {
		d := ShortBreakDuration()
		if d < 3*time.Minute || d > 10*time.Minute {
			t.Errorf("ShortBreakDuration() = %v, want 3–10 min", d)
		}
	}
}

func TestNightTrickleDelay_InRange(t *testing.T) {
	for i := 0; i < 50; i++ {
		d := NightTrickleDelay()
		if d < 20*time.Minute || d > 50*time.Minute {
			t.Errorf("NightTrickleDelay() = %v, want 20–50 min", d)
		}
	}
}
