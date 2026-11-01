package persona

import (
	"os"
	"path/filepath"
	"testing"
)

const testTimelinesYAML = `
ghosts_personas:
  test-ws1:
    character: Test User
    sam: test.user
    ad_domain: test.local
    netbios: TEST
    homepage: www.test.com
    has_owa_inbox: true
    browse_urls: [www.example.com]
`

const testOverridesYAML = `
ghosts_overrides:
  test-ws1:
    pace: obsessive
    active_hours:
      start: 09:00:00
      end: 17:00:00
    os: windows
    phrases:
      - "test phrase one\n"
      - "test phrase two\n"
    doc_paths:
      - '\\test-fs\share$\doc.docx'
`

func writePersonaFiles(t *testing.T, tlYAML, ovYAML string) (string, string) {
	t.Helper()
	dir := t.TempDir()
	tl := filepath.Join(dir, "timelines.yml")
	ov := filepath.Join(dir, "overrides.yml")
	if err := os.WriteFile(tl, []byte(tlYAML), 0600); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(ov, []byte(ovYAML), 0600); err != nil {
		t.Fatal(err)
	}
	return tl, ov
}

func TestLoad_Basic(t *testing.T) {
	tl, ov := writePersonaFiles(t, testTimelinesYAML, testOverridesYAML)
	personas, err := Load(tl, ov)
	if err != nil {
		t.Fatalf("Load: %v", err)
	}
	if len(personas) != 1 {
		t.Fatalf("expected 1 persona, got %d", len(personas))
	}
	p := personas[0]
	if p.Hostname != "test-ws1" {
		t.Errorf("hostname = %q, want test-ws1", p.Hostname)
	}
	if p.SAM != "test.user" {
		t.Errorf("sam = %q, want test.user", p.SAM)
	}
	if p.Pace != "obsessive" {
		t.Errorf("pace = %q, want obsessive", p.Pace)
	}
	if p.OS != "windows" {
		t.Errorf("os = %q, want windows", p.OS)
	}
	if len(p.Phrases) != 2 {
		t.Errorf("phrases len = %d, want 2", len(p.Phrases))
	}
	if len(p.DocPaths) != 1 {
		t.Errorf("doc_paths len = %d, want 1", len(p.DocPaths))
	}
}

func TestLoad_DefaultOS(t *testing.T) {
	tl, ov := writePersonaFiles(t, testTimelinesYAML, "ghosts_overrides: {}")
	personas, err := Load(tl, ov)
	if err != nil {
		t.Fatalf("Load: %v", err)
	}
	if personas[0].OS != "windows" {
		t.Errorf("default OS = %q, want windows", personas[0].OS)
	}
}

func TestLoad_MacOS(t *testing.T) {
	ov := `
ghosts_overrides:
  test-ws1:
    os: macos
    doc_paths: ["/Volumes/share/doc.docx"]
`
	tl, ovPath := writePersonaFiles(t, testTimelinesYAML, ov)
	personas, err := Load(tl, ovPath)
	if err != nil {
		t.Fatalf("Load: %v", err)
	}
	p := personas[0]
	if p.OS != "macos" {
		t.Errorf("OS = %q, want macos", p.OS)
	}
	if len(p.DocPaths) != 1 {
		t.Errorf("doc_paths len = %d, want 1", len(p.DocPaths))
	}
}

func TestLoad_DefaultActiveHours(t *testing.T) {
	tl, ov := writePersonaFiles(t, testTimelinesYAML, "ghosts_overrides: {}")
	personas, err := Load(tl, ov)
	if err != nil {
		t.Fatalf("Load: %v", err)
	}
	p := personas[0]
	if p.ActiveStart != "08:00:00" {
		t.Errorf("ActiveStart = %q, want 08:00:00", p.ActiveStart)
	}
	if p.ActiveEnd != "18:00:00" {
		t.Errorf("ActiveEnd = %q, want 18:00:00", p.ActiveEnd)
	}
}

func TestDeriveWindows(t *testing.T) {
	personas := []Persona{
		{Hostname: "test", ActiveStart: "09:00:00", ActiveEnd: "17:00:00"},
	}
	if err := DeriveWindows(personas, "+00:00"); err != nil {
		t.Fatalf("DeriveWindows: %v", err)
	}
	if personas[0].ActiveWindow[0].IsZero() || personas[0].ActiveWindow[1].IsZero() {
		t.Error("active window not set after DeriveWindows")
	}
}

func TestLoad_ReconLegsIgnored(t *testing.T) {
	ov := `
ghosts_overrides:
  test-ws1:
    recon_legs:
      fire_leaf_subnet_octet: 10
      dos_rate_per_second: 20
`
	tl, ovPath := writePersonaFiles(t, testTimelinesYAML, ov)
	personas, err := Load(tl, ovPath)
	if err != nil {
		t.Fatalf("Load with recon_legs should not error: %v", err)
	}
	if len(personas) != 1 {
		t.Fatalf("expected 1 persona, got %d", len(personas))
	}
}
