// Package persona loads the FGNW persona data that sasori uses to
// schedule and shape per-character activity.  It reads the same two YAML files
// the GHOSTS Ansible playbook reads, so the emulator and GHOSTS always agree on
// who lives on which workstation and when they work.
package persona

import (
	"fmt"
	"os"
	"time"

	"gopkg.in/yaml.v3"
)

// Persona is the merged view of one FGNW character's emulation parameters.
type Persona struct {
	Hostname    string
	Character   string
	SAM         string
	ADDomain    string
	Netbios     string
	Homepage    string
	HasOWAInbox bool
	BrowseURLs  []string

	// From overrides
	SignatureURLs []string
	Pace          string   // "obsessive" | "normal" | "idle"
	ActiveStart   string   // local time, e.g. "08:00:00"
	ActiveEnd     string   // local time, e.g. "18:00:00"
	AdminActivity bool
	Note          string
	OS            string   // "windows" (default) or "macos"
	Phrases       []string // optional typed phrases; scheduler falls back to built-in if empty
	DocPaths      []string // optional decoy document paths (UNC on Windows, Unix on macOS)

	// Derived
	ActiveWindow [2]time.Time // filled by DeriveWindows()
}

// IsActiveAt returns true if t falls inside the persona's active window.
// Handles midnight-crossing windows (ActiveStart > ActiveEnd in wall-clock).
func (p *Persona) IsActiveAt(t time.Time) bool {
	start := p.ActiveWindow[0]
	end := p.ActiveWindow[1]
	if start.IsZero() || end.IsZero() {
		return true // no window set — always active
	}
	if start.Before(end) {
		return !t.Before(start) && t.Before(end)
	}
	// Wraps midnight
	return !t.Before(start) || t.Before(end)
}

// --- YAML structures --------------------------------------------------------

type timelinesFile struct {
	GhostsPersonas map[string]timelineEntry `yaml:"ghosts_personas"`
}

type timelineEntry struct {
	Character   string   `yaml:"character"`
	SAM         string   `yaml:"sam"`
	ADDomain    string   `yaml:"ad_domain"`
	Netbios     string   `yaml:"netbios"`
	Homepage    string   `yaml:"homepage"`
	HasOWAInbox bool     `yaml:"has_owa_inbox"`
	BrowseURLs  []string `yaml:"browse_urls"`
}

type overridesFile struct {
	GhostsOverrides map[string]overrideEntry `yaml:"ghosts_overrides"`
}

type beliefEntry struct {
	Name       string  `yaml:"name"`
	Likelihood float64 `yaml:"likelihood"`
}

type knowledgeEntry struct {
	Topic string `yaml:"topic"`
	Value int    `yaml:"value"`
}

type overrideEntry struct {
	SignatureURLs  []string          `yaml:"signature_urls"`
	Pace           string            `yaml:"pace"`
	ActiveHours    *activeHoursEntry `yaml:"active_hours"`
	AdminActivity  bool              `yaml:"admin_activity"`
	Note           string            `yaml:"note"`
	OS             string            `yaml:"os"`       // "windows" (default) or "macos"
	Phrases        []string          `yaml:"phrases"`  // optional typed phrases for sasori
	DocPaths       []string          `yaml:"doc_paths"` // optional decoy document paths for sasori

	// The following fields are consumed by GHOSTS, not sasori.
	Beliefs         []beliefEntry    `yaml:"beliefs"`
	KnowledgeTopics []knowledgeEntry `yaml:"knowledge_topics"`
	// ReconLegs is an Akatsuki-only GHOSTS field for the intel campaign beat
	// (DoS target subnet, rate, duration). Intentionally not modelled in sasori;
	// GHOSTS handles it via timeline entries.
	ReconLegs interface{} `yaml:"recon_legs"`
}

type activeHoursEntry struct {
	Start string `yaml:"start"`
	End   string `yaml:"end"`
}

// Load reads persona-timelines.yml and persona-overrides.yml and returns a
// merged slice of Persona values, one per GHOSTS client host.
func Load(timelinesPath, overridesPath string) ([]Persona, error) {
	tl, err := loadTimelines(timelinesPath)
	if err != nil {
		return nil, fmt.Errorf("load timelines: %w", err)
	}
	ov, err := loadOverrides(overridesPath)
	if err != nil {
		return nil, fmt.Errorf("load overrides: %w", err)
	}

	personas := make([]Persona, 0, len(tl.GhostsPersonas))
	for hostname, te := range tl.GhostsPersonas {
		p := Persona{
			Hostname:    hostname,
			Character:   te.Character,
			SAM:         te.SAM,
			ADDomain:    te.ADDomain,
			Netbios:     te.Netbios,
			Homepage:    te.Homepage,
			HasOWAInbox: te.HasOWAInbox,
			BrowseURLs:  te.BrowseURLs,
			Pace:        "normal",
			ActiveStart: "08:00:00",
			ActiveEnd:   "18:00:00",
			OS:          "windows",
		}
		if oe, ok := ov.GhostsOverrides[hostname]; ok {
			if len(oe.SignatureURLs) > 0 {
				p.SignatureURLs = oe.SignatureURLs
			}
			if oe.Pace != "" {
				p.Pace = oe.Pace
			}
			if oe.ActiveHours != nil {
				if oe.ActiveHours.Start != "" {
					p.ActiveStart = oe.ActiveHours.Start
				}
				if oe.ActiveHours.End != "" {
					p.ActiveEnd = oe.ActiveHours.End
				}
			}
			p.AdminActivity = oe.AdminActivity
			p.Note = oe.Note
			if oe.OS != "" {
				p.OS = oe.OS
			}
			if len(oe.Phrases) > 0 {
				p.Phrases = oe.Phrases
			}
			if len(oe.DocPaths) > 0 {
				p.DocPaths = oe.DocPaths
			}
		}
		personas = append(personas, p)
	}
	return personas, nil
}

// DeriveWindows fills each persona's ActiveWindow based on their ActiveStart /
// ActiveEnd strings and the supplied timezone offset (e.g. "+10:00").
// Call this once after Load() with the range's local timezone.
func DeriveWindows(personas []Persona, tzOffset string) error {
	now := time.Now()
	loc, err := parseOffset(tzOffset)
	if err != nil {
		return err
	}
	for i := range personas {
		p := &personas[i]
		start, err := parseTimeOfDay(p.ActiveStart, now, loc)
		if err != nil {
			return fmt.Errorf("persona %s start: %w", p.Hostname, err)
		}
		end, err := parseTimeOfDay(p.ActiveEnd, now, loc)
		if err != nil {
			return fmt.Errorf("persona %s end: %w", p.Hostname, err)
		}
		p.ActiveWindow = [2]time.Time{start, end}
	}
	return nil
}

// --- helpers ----------------------------------------------------------------

func loadTimelines(path string) (timelinesFile, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return timelinesFile{}, err
	}
	var f timelinesFile
	return f, yaml.Unmarshal(data, &f)
}

func loadOverrides(path string) (overridesFile, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return overridesFile{}, err
	}
	var f overridesFile
	return f, yaml.Unmarshal(data, &f)
}

func parseTimeOfDay(s string, refDay time.Time, loc *time.Location) (time.Time, error) {
	var h, m, sec int
	if _, err := fmt.Sscanf(s, "%d:%d:%d", &h, &m, &sec); err != nil {
		return time.Time{}, fmt.Errorf("cannot parse time-of-day %q: %w", s, err)
	}
	return time.Date(refDay.Year(), refDay.Month(), refDay.Day(), h, m, sec, 0, loc), nil
}

// parseOffset parses a UTC offset string like "+10:00" or "-05:30" into a
// *time.Location.
func parseOffset(s string) (*time.Location, error) {
	if s == "" || s == "UTC" || s == "+00:00" {
		return time.UTC, nil
	}
	sign := 1
	if len(s) > 0 && s[0] == '-' {
		sign = -1
		s = s[1:]
	} else if len(s) > 0 && s[0] == '+' {
		s = s[1:]
	}
	var h, m int
	if _, err := fmt.Sscanf(s, "%d:%d", &h, &m); err != nil {
		return nil, fmt.Errorf("cannot parse UTC offset %q: %w", s, err)
	}
	offset := sign * (h*3600 + m*60)
	return time.FixedZone(fmt.Sprintf("UTC%+d", sign*(h*100+m)), offset), nil
}
