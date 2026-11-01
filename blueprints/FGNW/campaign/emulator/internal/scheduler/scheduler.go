package scheduler

import (
	"context"
	"fmt"
	"log/slog"
	"sync"
	"time"

	"github.com/get-sybers/fgnw-emulator/internal/activity"
	"github.com/get-sybers/fgnw-emulator/internal/persona"
	"github.com/get-sybers/fgnw-emulator/internal/proxmox"
)

// Event is one emitted activity record — written to the activity log and
// optionally forwarded to the GHOSTS API.
type Event struct {
	Time     time.Time
	Hostname string
	VMID     int
	Kind     activity.Kind
	Note     string
	Err      error
}

// Scheduler manages per-persona goroutines.
type Scheduler struct {
	pve       *proxmox.Client
	vmMap     map[string]proxmox.VMInfo // hostname → VM
	personas  []persona.Persona
	passwords map[string]string // hostname → plaintext password
	dryRun    bool

	mu      sync.RWMutex
	paused  bool
	log     []Event      // ring buffer (last 500 events)
	eventCh chan Event    // broadcast to API watchers
	cancel  context.CancelFunc
}

// New creates a Scheduler.  passwords maps inventory hostnames to the
// domain user's plaintext password (used for unlock injection).
func New(
	pve *proxmox.Client,
	vmMap map[string]proxmox.VMInfo,
	personas []persona.Persona,
	passwords map[string]string,
	dryRun bool,
) *Scheduler {
	return &Scheduler{
		pve:       pve,
		vmMap:     vmMap,
		personas:  personas,
		passwords: passwords,
		dryRun:    dryRun,
		eventCh:   make(chan Event, 256),
	}
}

// Start launches one goroutine per persona and returns immediately.
// Call Stop() to shut everything down.
func (s *Scheduler) Start(ctx context.Context) {
	ctx, s.cancel = context.WithCancel(ctx)
	for i := range s.personas {
		go s.runPersona(ctx, &s.personas[i])
	}
}

// Stop signals all goroutines to exit and waits briefly.
func (s *Scheduler) Stop() {
	if s.cancel != nil {
		s.cancel()
	}
}

// Pause suspends activity injection without stopping goroutines.
func (s *Scheduler) Pause() {
	s.mu.Lock()
	s.paused = true
	s.mu.Unlock()
}

// Resume resumes injection after a Pause.
func (s *Scheduler) Resume() {
	s.mu.Lock()
	s.paused = false
	s.mu.Unlock()
}

// RecentEvents returns up to n recent events newest-first.
func (s *Scheduler) RecentEvents(n int) []Event {
	s.mu.RLock()
	defer s.mu.RUnlock()
	out := make([]Event, 0, n)
	for i := len(s.log) - 1; i >= 0 && len(out) < n; i-- {
		out = append(out, s.log[i])
	}
	return out
}

// Events returns the event broadcast channel (read-only).
func (s *Scheduler) Events() <-chan Event { return s.eventCh }

// TriggerActivity immediately runs a specific activity for a persona,
// bypassing the normal schedule.  Used by the API's POST /trigger endpoint.
func (s *Scheduler) TriggerActivity(hostname string, kind activity.Kind) error {
	var p *persona.Persona
	for i := range s.personas {
		if s.personas[i].Hostname == hostname {
			p = &s.personas[i]
			break
		}
	}
	if p == nil {
		return fmt.Errorf("persona %q not found", hostname)
	}
	vm, ok := s.vmMap[hostname]
	if !ok {
		return fmt.Errorf("VM for %q not in vm map", hostname)
	}
	return s.execActivity(p, vm.VMID, kind)
}

// --- per-persona loop -------------------------------------------------------

func (s *Scheduler) runPersona(ctx context.Context, p *persona.Persona) {
	vm, ok := s.vmMap[p.Hostname]
	if !ok {
		slog.Warn("scheduler: no VM found for persona, skipping",
			"hostname", p.Hostname, "character", p.Character)
		return
	}
	slog.Info("scheduler: persona goroutine started",
		"hostname", p.Hostname, "character", p.Character,
		"pace", p.Pace, "vmid", vm.VMID)

	weights := activity.PaceWeights(p.Pace)
	lunchDone := false // reset each calendar day

	for {
		delay := NextDelay(p.Pace)

		select {
		case <-ctx.Done():
			return
		case <-time.After(delay):
		}

		now := time.Now()

		// Skip if paused.
		s.mu.RLock()
		paused := s.paused
		s.mu.RUnlock()
		if paused {
			continue
		}

		// Skip if outside active window.
		if !p.IsActiveAt(now) {
			continue
		}

		// Lunch lock-cycle: once per day around noon.
		if IsLunchWindow(now) && !lunchDone {
			lunchDone = true
			slog.Info("scheduler: lunch lock cycle", "hostname", p.Hostname)
			sc := s.sessionController(p, vm.VMID)
			if err := sc.LockUnlockCycle(LunchIdleDuration(), 55); err != nil {
				s.emit(p, vm.VMID, activity.KindLock, err)
			} else {
				s.emit(p, vm.VMID, activity.KindUnlock, nil)
			}
			continue
		}
		if !IsLunchWindow(now) {
			lunchDone = false // reset for tomorrow
		}

		// Normal activity.
		kind := activity.Sample(weights)
		if err := s.execActivity(p, vm.VMID, kind); err != nil {
			slog.Error("scheduler: activity error",
				"hostname", p.Hostname, "kind", kind, "err", err)
			s.emit(p, vm.VMID, kind, err)
		} else {
			s.emit(p, vm.VMID, kind, nil)
		}
	}
}

// execActivity dispatches one activity kind for a persona on vmid.
func (s *Scheduler) execActivity(p *persona.Persona, vmid int, kind activity.Kind) error {
	sc := s.sessionController(p, vmid)

	switch kind {
	case activity.KindLock:
		return sc.Lock()

	case activity.KindUnlock:
		// Only meaningful if the screen is currently locked; we attempt it
		// regardless — the lock screen ignores extra input if not locked.
		return sc.Unlock(55)

	case activity.KindLogoff:
		return sc.Logoff()

	case activity.KindMouseMove, activity.KindIdleJitter:
		return sc.MouseJitter()

	case activity.KindType:
		// Type a short persona-flavoured phrase into the foreground window.
		phrase := personaPhrase(p)
		return s.pve.TypeString(vmid, phrase, 120, 0.02)

	case activity.KindOpenFile:
		// Launch a decoy document from the village share via the Guest Agent.
		path := personaDocPath(p)
		if path == "" {
			return nil
		}
		_, err := s.pve.AgentExec(vmid,
			`C:\Windows\explorer.exe`,
			[]string{path},
			10*time.Second)
		return err
	}
	return nil
}

func (s *Scheduler) sessionController(p *persona.Persona, vmid int) *activity.SessionController {
	pw := s.passwords[p.Hostname]
	return activity.NewSessionController(s.pve, vmid, p.ADDomain, p.SAM, pw, s.dryRun)
}

func (s *Scheduler) emit(p *persona.Persona, vmid int, kind activity.Kind, err error) {
	ev := Event{
		Time:     time.Now(),
		Hostname: p.Hostname,
		VMID:     vmid,
		Kind:     kind,
		Err:      err,
	}
	// Append to ring buffer (cap 500).
	s.mu.Lock()
	s.log = append(s.log, ev)
	if len(s.log) > 500 {
		s.log = s.log[len(s.log)-500:]
	}
	s.mu.Unlock()

	// Non-blocking broadcast.
	select {
	case s.eventCh <- ev:
	default:
	}
}

// --- content helpers --------------------------------------------------------

// personaPhrase returns a short typed phrase flavoured for the persona.
// These are the kinds of things a real user types into Notepad, a chat box,
// or a search bar — mundane, brief, in-character.
func personaPhrase(p *persona.Persona) string {
	phrases := map[string][]string{
		"konoha-ws1": {
			"mission report draft\n",
			"ichiraku ramen lunch order\n",
			"shadow clone training notes\n",
			"hokage office memo\n",
		},
		"konoha-ws2": {
			"tactical analysis - Q3\n",
			"nara clan deer census update\n",
			"shadow possession range notes\n",
			"mission debrief draft\n",
		},
		"konoha-ws3": {
			"ANBU op summary\n",
			"jonin briefing notes\n",
			"training schedule review\n",
		},
		"konoha-ws4": {
			"hospital budget report\n",
			"medical-nin roster update\n",
			"hokage office policy draft\n",
		},
		"konoha-ws5": {
			"youth training programme\n",
			"team 9 mission log\n",
			"morning workout notes\n",
		},
		"oto-ws1": {
			"research notes - stage 2\n",
			"technique catalogue update\n",
			"experimental results log\n",
		},
		"akatsuki-ws1": {
			"operational planning notes\n",
			"border intelligence update\n",
			"member task assignments\n",
		},
		"akatsuki-ws2": {
			"observation log - leaf\n",
			"reconnaissance summary\n",
			"cross-village intel notes\n",
		},
		"suna-ws1": {
			"kazekage office memo\n",
			"sand village security review\n",
			"allied shinobi coordination\n",
		},
	}
	options, ok := phrases[p.Hostname]
	if !ok || len(options) == 0 {
		return "meeting notes\n"
	}
	rngMu.Lock()
	idx := rng.Intn(len(options))
	rngMu.Unlock()
	return options[idx]
}

// personaDocPath returns a UNC path to a decoy document on the village share
// for the persona to "open".  The paths mirror the filesystem corpus staged
// by the fgnw_decoy_files role.
func personaDocPath(p *persona.Persona) string {
	docs := map[string][]string{
		"konoha-ws1": {
			`\\konoha-fs\leaf$\Mission Reports\naruto_uzumaki_field_report.docx`,
			`\\konoha-fs\leaf$\Personnel\uzumaki_clan_register.docx`,
		},
		"konoha-ws2": {
			`\\konoha-fs\leaf$\Intelligence\tactical_analysis_q3.docx`,
			`\\konoha-fs\leaf$\Clan Records\nara_shadow_techniques.docx`,
		},
		"konoha-ws3": {
			`\\konoha-fs\leaf$\ANBU\classified_op_log.docx`,
			`\\konoha-fs\leaf$\Personnel\jonin_roster.xlsx`,
		},
		"konoha-ws4": {
			`\\konoha-fs\leaf$\Medical\hospital_budget_fy.xlsx`,
			`\\konoha-fs\leaf$\Hokage Office\village_policy_draft.docx`,
		},
		"konoha-ws5": {
			`\\konoha-fs\leaf$\Training\team9_mission_log.docx`,
		},
		"oto-ws1": {
			`\\oto-fs\sound$\Research\forbidden_technique_notes.docx`,
		},
		"akatsuki-ws1": {
			`\\akatsuki-fs\dark$\Operation Logs\active\tailed_beast_capture_order.docx`,
		},
		"akatsuki-ws2": {
			`\\akatsuki-fs\dark$\Intelligence Files\village_weaknesses_assessment.xlsx`,
			`\\akatsuki-fs\dark$\Intelligence Files\jinchuriki_host_profiles.xlsx`,
		},
		"suna-ws1": {
			`\\suna-fs\sand$\Kazekage Office\security_review.docx`,
		},
	}
	options, ok := docs[p.Hostname]
	if !ok || len(options) == 0 {
		return ""
	}
	rngMu.Lock()
	idx := rng.Intn(len(options))
	rngMu.Unlock()
	return options[idx]
}
