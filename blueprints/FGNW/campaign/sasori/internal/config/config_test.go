package config

import (
	"os"
	"testing"
)

func setEnv(t *testing.T, pairs ...string) {
	t.Helper()
	for i := 0; i+1 < len(pairs); i += 2 {
		t.Setenv(pairs[i], pairs[i+1])
	}
}

func baseEnv(t *testing.T) {
	t.Helper()
	setEnv(t,
		"PVE_HOST", "https://pve01:8006",
		"PVE_TOKEN_ID", "emulator",
		"PVE_SECRET", "secret123",
		"RANGE_NUMBER", "1",
	)
}

func TestLoad_Required(t *testing.T) {
	baseEnv(t)
	cfg, err := Load()
	if err != nil {
		t.Fatalf("Load: %v", err)
	}
	if cfg.PVEHost != "https://pve01:8006" {
		t.Errorf("PVEHost = %q", cfg.PVEHost)
	}
	if cfg.RangeNumber != 1 {
		t.Errorf("RangeNumber = %d, want 1", cfg.RangeNumber)
	}
}

func TestLoad_Defaults(t *testing.T) {
	baseEnv(t)
	cfg, err := Load()
	if err != nil {
		t.Fatalf("Load: %v", err)
	}
	if cfg.PVENode != "pve" {
		t.Errorf("PVENode = %q, want pve", cfg.PVENode)
	}
	if cfg.APIListenAddr != ":8080" {
		t.Errorf("APIListenAddr = %q, want :8080", cfg.APIListenAddr)
	}
	if cfg.DryRun {
		t.Errorf("DryRun should default to false")
	}
}

func TestLoad_MissingRequired(t *testing.T) {
	// Clear all relevant env vars.
	for _, k := range []string{"PVE_HOST", "PVE_TOKEN_ID", "PVE_SECRET", "RANGE_NUMBER"} {
		os.Unsetenv(k)
	}
	t.Setenv("RANGE_NUMBER", "1")
	_, err := Load()
	if err == nil {
		t.Fatal("expected error when PVE_HOST/PVE_TOKEN_ID/PVE_SECRET missing")
	}
}

func TestLoad_InvalidRangeNumber(t *testing.T) {
	baseEnv(t)
	t.Setenv("RANGE_NUMBER", "not-a-number")
	_, err := Load()
	if err == nil {
		t.Fatal("expected error for non-integer RANGE_NUMBER")
	}
}

func TestLoad_ZeroRangeNumber(t *testing.T) {
	baseEnv(t)
	t.Setenv("RANGE_NUMBER", "0")
	_, err := Load()
	if err == nil {
		t.Fatal("expected error for RANGE_NUMBER=0")
	}
}

func TestLoad_DryRunTrue(t *testing.T) {
	baseEnv(t)
	t.Setenv("DRY_RUN", "true")
	cfg, err := Load()
	if err != nil {
		t.Fatalf("Load: %v", err)
	}
	if !cfg.DryRun {
		t.Errorf("DryRun should be true")
	}
}

func TestLoad_PVEInsecure(t *testing.T) {
	baseEnv(t)
	t.Setenv("PVE_INSECURE", "1")
	cfg, err := Load()
	if err != nil {
		t.Fatalf("Load: %v", err)
	}
	if !cfg.PVEInsecure {
		t.Errorf("PVEInsecure should be true")
	}
}
