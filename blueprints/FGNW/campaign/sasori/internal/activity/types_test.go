package activity

import "testing"

func TestPaceWeights_NonEmpty(t *testing.T) {
	for _, pace := range []string{"obsessive", "normal", "idle", "unknown"} {
		w := PaceWeights(pace)
		if len(w) == 0 {
			t.Errorf("PaceWeights(%q) returned empty slice", pace)
		}
		total := 0
		for _, e := range w {
			if e.Weight < 0 {
				t.Errorf("PaceWeights(%q): negative weight %d for %q", pace, e.Weight, e.Kind)
			}
			total += e.Weight
		}
		if total <= 0 {
			t.Errorf("PaceWeights(%q) total weight = %d, want > 0", pace, total)
		}
	}
}

func TestPaceWeights_ObsessiveHeavyOnType(t *testing.T) {
	w := PaceWeights("obsessive")
	var typeW, totalW int
	for _, e := range w {
		totalW += e.Weight
		if e.Kind == KindType {
			typeW = e.Weight
		}
	}
	if float64(typeW)/float64(totalW) < 0.3 {
		t.Errorf("obsessive pace should weight KindType heavily, got %d/%d", typeW, totalW)
	}
}

func TestSample_KnownKind(t *testing.T) {
	weights := PaceWeights("normal")
	for i := 0; i < 200; i++ {
		k := Sample(weights)
		if k == "" {
			t.Fatalf("Sample returned empty Kind on iteration %d", i)
		}
	}
}

func TestSample_EmptyWeights_DefaultsToIdleJitter(t *testing.T) {
	if k := Sample([]Weight{}); k != KindIdleJitter {
		t.Errorf("Sample(empty) = %q, want %q", k, KindIdleJitter)
	}
}

func TestSample_ZeroTotalWeight_DefaultsToIdleJitter(t *testing.T) {
	w := []Weight{{Kind: KindLock, Weight: 0}, {Kind: KindType, Weight: 0}}
	if k := Sample(w); k != KindIdleJitter {
		t.Errorf("Sample(zero weights) = %q, want %q", k, KindIdleJitter)
	}
}

func TestSample_SingleWeight(t *testing.T) {
	w := []Weight{{Kind: KindLock, Weight: 100}}
	for i := 0; i < 20; i++ {
		if k := Sample(w); k != KindLock {
			t.Errorf("Sample(lock-only) = %q, want lock on iteration %d", k, i)
		}
	}
}
