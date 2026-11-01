// sasori: hypervisor-level user activity injection for the FGNW range.
//
// Runs in an LXC on the Proxmox host, reads the FGNW persona configs, and
// drives per-persona goroutines that inject keyboard input, lock/unlock cycles,
// and file-open actions into each workstation VM via:
//
//   - Proxmox HMP monitor endpoint (sendkey) — keyboard input at the QEMU
//     emulation layer; completely transparent to the guest OS.
//   - Proxmox QEMU Guest Agent exec endpoint — high-level guest operations
//     (file open, logoff, process check) run as SYSTEM inside the VM.
//
// Exposes a REST API (default :8080) for status, manual triggers, and a
// Server-Sent Events stream of live activity.
//
// Required environment variables:
//
//	PVE_HOST        Proxmox base URL, e.g. https://pve01:8006
//	PVE_USER        API token user, e.g. emulator@pve
//	PVE_TOKEN_ID    API token ID (the part after the !)
//	PVE_SECRET      API token secret
//	RANGE_NUMBER    Ludus range number (integer)
//
// Optional:
//
//	PVE_NODE               Proxmox node name (default: pve)
//	PVE_INSECURE           skip TLS verification (default: false)
//	PERSONA_TIMELINES      path to persona-timelines.yml
//	PERSONA_OVERRIDES      path to persona-overrides.yml
//	PERSONA_PASSWORDS      path to a YAML file mapping hostname→password
//	GHOSTS_API_URL         GHOSTS API URL for activity reporting
//	API_LISTEN             API listen address (default: :8080)
//	API_TOKEN              Bearer token for API auth (default: no auth)
//	TZ_OFFSET              UTC offset of the range (default: +00:00)
//	DRY_RUN                log actions but do not inject input (default: false)
package main

import (
	"context"
	"log/slog"
	"os"
	"os/signal"
	"syscall"

	"github.com/get-sybers/sasori/internal/api"
	"github.com/get-sybers/sasori/internal/config"
	"github.com/get-sybers/sasori/internal/persona"
	"github.com/get-sybers/sasori/internal/proxmox"
	"github.com/get-sybers/sasori/internal/scheduler"
)

const version = "0.1.0"

func main() {
	slog.SetDefault(slog.New(slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{
		Level: slog.LevelInfo,
	})))

	cfg, err := config.Load()
	if err != nil {
		slog.Error("config", "err", err)
		os.Exit(1)
	}

	slog.Info("sasori starting",
		"version", version,
		"range", cfg.RangeNumber,
		"dry_run", cfg.DryRun,
		"api", cfg.APIListenAddr)

	// --- Proxmox client -------------------------------------------------
	pve := proxmox.NewClient(
		cfg.PVEHost, cfg.PVEUser, cfg.PVETokenID, cfg.PVESecret,
		cfg.PVENode, cfg.PVEInsecure,
	)

	// --- Load personas --------------------------------------------------
	personas, err := persona.Load(cfg.PersonaTimelinesPath, cfg.PersonaOverridesPath)
	if err != nil {
		slog.Error("load personas", "err", err)
		os.Exit(1)
	}
	slog.Info("personas loaded", "count", len(personas))

	tzOffset := os.Getenv("TZ_OFFSET")
	if tzOffset == "" {
		tzOffset = "+00:00"
	}
	if err := persona.DeriveWindows(personas, tzOffset); err != nil {
		slog.Error("derive windows", "err", err)
		os.Exit(1)
	}

	// --- Discover VMs ---------------------------------------------------
	hostnames := make([]string, len(personas))
	for i, p := range personas {
		hostnames[i] = p.Hostname
	}
	vmMap, err := pve.BuildVMMap(hostnames)
	if err != nil {
		slog.Error("discover VMs", "err", err)
		os.Exit(1)
	}
	slog.Info("VMs mapped", "found", len(vmMap), "expected", len(hostnames))
	for _, h := range hostnames {
		if vm, ok := vmMap[h]; ok {
			slog.Info("vm mapped", "hostname", h, "vmid", vm.VMID, "status", vm.Status)
		} else {
			slog.Warn("vm not found", "hostname", h)
		}
	}

	// --- Load per-persona passwords -------------------------------------
	passwords, err := loadPasswords(os.Getenv("PERSONA_PASSWORDS"))
	if err != nil {
		slog.Warn("passwords file not loaded (unlock injection disabled)", "err", err)
		passwords = map[string]string{}
	}

	// --- Scheduler ------------------------------------------------------
	sched := scheduler.New(pve, vmMap, personas, passwords, cfg.DryRun)

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	sched.Start(ctx)
	slog.Info("scheduler started", "goroutines", len(personas))

	// --- API server -----------------------------------------------------
	apiSrv := api.New(cfg.APIListenAddr, cfg.APIToken, personas, vmMap, sched, version)
	go func() {
		if err := apiSrv.Start(ctx); err != nil {
			slog.Error("api server", "err", err)
		}
	}()

	// --- Wait for shutdown signal ----------------------------------------
	sig := make(chan os.Signal, 1)
	signal.Notify(sig, syscall.SIGINT, syscall.SIGTERM)
	<-sig
	slog.Info("shutdown signal received")
	sched.Stop()
	cancel()
	slog.Info("sasori stopped")
}

// loadPasswords reads a simple YAML file of the form:
//
//	konoha-ws1: "P@ssw0rd"
//	konoha-ws2: "An0therPass"
//
// Returns an empty map and an error if the file is missing or unparseable.
func loadPasswords(path string) (map[string]string, error) {
	if path == "" {
		path = "/etc/sasori/passwords.yml"
	}
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	// Minimal YAML parse — just a flat map[string]string.
	// We use the persona package's yaml import transitively; call yaml.Unmarshal
	// directly here by importing gopkg.in/yaml.v3.
	result := map[string]string{}
	// Manual parse to avoid another import in main; passwords.yml is a flat map.
	lines := splitLines(string(data))
	for _, line := range lines {
		if len(line) == 0 || line[0] == '#' {
			continue
		}
		colon := -1
		for i, b := range line {
			if b == ':' {
				colon = i
				break
			}
		}
		if colon < 0 {
			continue
		}
		key := trim(line[:colon])
		val := trim(line[colon+1:])
		// Strip surrounding quotes if present.
		if len(val) >= 2 && val[0] == '"' && val[len(val)-1] == '"' {
			val = val[1 : len(val)-1]
		} else if len(val) >= 2 && val[0] == '\'' && val[len(val)-1] == '\'' {
			val = val[1 : len(val)-1]
		}
		if key != "" && val != "" {
			result[key] = val
		}
	}
	return result, nil
}

func splitLines(s string) []string {
	var lines []string
	cur := ""
	for _, r := range s {
		if r == '\n' {
			lines = append(lines, cur)
			cur = ""
		} else if r != '\r' {
			cur += string(r)
		}
	}
	if cur != "" {
		lines = append(lines, cur)
	}
	return lines
}

func trim(s string) string {
	start := 0
	for start < len(s) && (s[start] == ' ' || s[start] == '\t') {
		start++
	}
	end := len(s)
	for end > start && (s[end-1] == ' ' || s[end-1] == '\t') {
		end--
	}
	return s[start:end]
}
