// Package config loads and validates the sasori configuration from
// environment variables (primary) with an optional YAML file fallback.
package config

import (
	"fmt"
	"os"
	"strconv"
	"strings"
)

// Config is the full runtime configuration for sasori.
type Config struct {
	// Proxmox API connection
	PVEHost     string // e.g. "https://pve01.example.com:8006"
	PVEUser     string // e.g. "emulator@pve"
	PVETokenID  string // API token ID  (the part after the !)
	PVESecret   string // API token secret
	PVEInsecure bool   // skip TLS verification (dev only)
	PVENode     string // Proxmox node name the range VMs live on

	// Range identity
	RangeNumber int // Ludus range number; drives IP addressing (10.<N>.x.x)

	// Persona config paths (read from the FGNW campaign tree)
	PersonaTimelinesPath string // path to content/ghosts/persona-timelines.yml
	PersonaOverridesPath string // path to content/ghosts/persona-overrides.yml

	// GHOSTS API (optional — emulator reports activity back to ghost9)
	GhostsAPIURL string // e.g. "http://10.2.99.51:5000/api" — empty disables reporting

	// Emulator API server
	APIListenAddr string // e.g. ":8080"
	APIToken      string // Bearer token callers must present (empty = no auth)

	// Emulation behaviour
	DryRun bool // log activity but do not inject any input
}

// Load returns a Config populated from environment variables.
// Required variables are checked; missing ones return an error listing all gaps.
func Load() (*Config, error) {
	c := &Config{
		PVEHost:              env("PVE_HOST", ""),
		PVEUser:              env("PVE_USER", "emulator@pve"),
		PVETokenID:           env("PVE_TOKEN_ID", ""),
		PVESecret:            env("PVE_SECRET", ""),
		PVEInsecure:          envBool("PVE_INSECURE", false),
		PVENode:              env("PVE_NODE", "pve"),
		PersonaTimelinesPath: env("PERSONA_TIMELINES", "/etc/sasori/persona-timelines.yml"),
		PersonaOverridesPath: env("PERSONA_OVERRIDES", "/etc/sasori/persona-overrides.yml"),
		GhostsAPIURL:         env("GHOSTS_API_URL", ""),
		APIListenAddr:        env("API_LISTEN", ":8080"),
		APIToken:             env("API_TOKEN", ""),
		DryRun:               envBool("DRY_RUN", false),
	}

	// RangeNumber
	rn, err := strconv.Atoi(env("RANGE_NUMBER", "0"))
	if err != nil || rn <= 0 {
		return nil, fmt.Errorf("RANGE_NUMBER must be a positive integer, got %q", env("RANGE_NUMBER", "0"))
	}
	c.RangeNumber = rn

	var missing []string
	if c.PVEHost == "" {
		missing = append(missing, "PVE_HOST")
	}
	if c.PVETokenID == "" {
		missing = append(missing, "PVE_TOKEN_ID")
	}
	if c.PVESecret == "" {
		missing = append(missing, "PVE_SECRET")
	}
	if len(missing) > 0 {
		return nil, fmt.Errorf("required environment variables not set: %s", strings.Join(missing, ", "))
	}

	return c, nil
}

func env(key, def string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return def
}

func envBool(key string, def bool) bool {
	v := os.Getenv(key)
	if v == "" {
		return def
	}
	b, err := strconv.ParseBool(v)
	if err != nil {
		return def
	}
	return b
}
