// Package api exposes the fgnw-emulator REST API.
//
// Endpoints:
//
//	GET  /health
//	GET  /api/v1/personas
//	GET  /api/v1/personas/{hostname}
//	POST /api/v1/personas/{hostname}/trigger    body: {"activity":"lock|unlock|logoff|type|open_file|idle_jitter"}
//	GET  /api/v1/vms
//	POST /api/v1/scheduler/pause
//	POST /api/v1/scheduler/resume
//	GET  /api/v1/activity/recent               ?n=<count>
//	GET  /api/v1/activity/stream               Server-Sent Events
//
// All endpoints return JSON.  If APIToken is set in the config, every request
// must carry "Authorization: Bearer <token>" or receive 401.
package api

import (
	"context"
	"encoding/json"
	"fmt"
	"log/slog"
	"net/http"
	"strconv"
	"strings"
	"time"

	"github.com/get-sybers/fgnw-emulator/internal/activity"
	"github.com/get-sybers/fgnw-emulator/internal/persona"
	"github.com/get-sybers/fgnw-emulator/internal/proxmox"
	"github.com/get-sybers/fgnw-emulator/internal/scheduler"
)

// Server is the API HTTP server.
type Server struct {
	addr      string
	token     string
	personas  []persona.Persona
	vmMap     map[string]proxmox.VMInfo
	sched     *scheduler.Scheduler
	version   string
	startTime time.Time
	srv       *http.Server
}

// New creates the API server.  Call Start() to begin listening.
func New(
	addr, token string,
	personas []persona.Persona,
	vmMap map[string]proxmox.VMInfo,
	sched *scheduler.Scheduler,
	version string,
) *Server {
	s := &Server{
		addr: addr, token: token,
		personas: personas, vmMap: vmMap, sched: sched,
		version: version, startTime: time.Now(),
	}
	mux := http.NewServeMux()
	mux.HandleFunc("GET /health", s.handleHealth)
	mux.HandleFunc("GET /api/v1/personas", s.handleListPersonas)
	mux.HandleFunc("GET /api/v1/personas/{hostname}", s.handleGetPersona)
	mux.HandleFunc("POST /api/v1/personas/{hostname}/trigger", s.handleTrigger)
	mux.HandleFunc("GET /api/v1/vms", s.handleListVMs)
	mux.HandleFunc("POST /api/v1/scheduler/pause", s.handlePause)
	mux.HandleFunc("POST /api/v1/scheduler/resume", s.handleResume)
	mux.HandleFunc("GET /api/v1/activity/recent", s.handleRecentActivity)
	mux.HandleFunc("GET /api/v1/activity/stream", s.handleActivityStream)

	s.srv = &http.Server{
		Addr:         addr,
		Handler:      s.auth(mux),
		ReadTimeout:  15 * time.Second,
		WriteTimeout: 0, // SSE stream needs no write deadline
	}
	return s
}

// Start begins listening; returns when the context is cancelled.
func (s *Server) Start(ctx context.Context) error {
	go func() {
		<-ctx.Done()
		_ = s.srv.Shutdown(context.Background())
	}()
	slog.Info("api: listening", "addr", s.addr)
	if err := s.srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
		return err
	}
	return nil
}

// --- handlers ---------------------------------------------------------------

func (s *Server) handleHealth(w http.ResponseWriter, r *http.Request) {
	jsonOK(w, map[string]any{
		"status":    "ok",
		"version":   s.version,
		"uptime_s":  int(time.Since(s.startTime).Seconds()),
		"personas":  len(s.personas),
		"vms_known": len(s.vmMap),
	})
}

type personaView struct {
	Hostname      string   `json:"hostname"`
	Character     string   `json:"character"`
	SAM           string   `json:"sam"`
	Domain        string   `json:"domain"`
	Pace          string   `json:"pace"`
	ActiveStart   string   `json:"active_start"`
	ActiveEnd     string   `json:"active_end"`
	SignatureURLs []string `json:"signature_urls,omitempty"`
	VMID          int      `json:"vmid,omitempty"`
	VMStatus      string   `json:"vm_status,omitempty"`
}

func (s *Server) handleListPersonas(w http.ResponseWriter, r *http.Request) {
	out := make([]personaView, 0, len(s.personas))
	for _, p := range s.personas {
		out = append(out, s.toView(p))
	}
	jsonOK(w, out)
}

func (s *Server) handleGetPersona(w http.ResponseWriter, r *http.Request) {
	hostname := r.PathValue("hostname")
	for _, p := range s.personas {
		if p.Hostname == hostname {
			jsonOK(w, s.toView(p))
			return
		}
	}
	jsonErr(w, http.StatusNotFound, fmt.Sprintf("persona %q not found", hostname))
}

func (s *Server) handleTrigger(w http.ResponseWriter, r *http.Request) {
	hostname := r.PathValue("hostname")
	var body struct {
		Activity string `json:"activity"`
	}
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
		jsonErr(w, http.StatusBadRequest, "invalid JSON body")
		return
	}
	kind := activity.Kind(body.Activity)
	if err := s.sched.TriggerActivity(hostname, kind); err != nil {
		jsonErr(w, http.StatusBadRequest, err.Error())
		return
	}
	jsonOK(w, map[string]string{"status": "triggered", "hostname": hostname, "activity": body.Activity})
}

func (s *Server) handleListVMs(w http.ResponseWriter, r *http.Request) {
	type vmView struct {
		Hostname string `json:"hostname"`
		VMID     int    `json:"vmid"`
		Name     string `json:"name"`
		Status   string `json:"status"`
	}
	out := make([]vmView, 0, len(s.vmMap))
	for hostname, vm := range s.vmMap {
		out = append(out, vmView{
			Hostname: hostname,
			VMID:     vm.VMID,
			Name:     vm.Name,
			Status:   vm.Status,
		})
	}
	jsonOK(w, out)
}

func (s *Server) handlePause(w http.ResponseWriter, r *http.Request) {
	s.sched.Pause()
	jsonOK(w, map[string]string{"status": "paused"})
}

func (s *Server) handleResume(w http.ResponseWriter, r *http.Request) {
	s.sched.Resume()
	jsonOK(w, map[string]string{"status": "resumed"})
}

func (s *Server) handleRecentActivity(w http.ResponseWriter, r *http.Request) {
	n := 50
	if qn := r.URL.Query().Get("n"); qn != "" {
		if v, err := strconv.Atoi(qn); err == nil && v > 0 {
			n = v
		}
	}
	if n > 500 {
		n = 500
	}
	events := s.sched.RecentEvents(n)
	type evView struct {
		Time     string `json:"time"`
		Hostname string `json:"hostname"`
		VMID     int    `json:"vmid"`
		Kind     string `json:"kind"`
		Error    string `json:"error,omitempty"`
	}
	out := make([]evView, 0, len(events))
	for _, e := range events {
		ev := evView{
			Time:     e.Time.Format(time.RFC3339),
			Hostname: e.Hostname,
			VMID:     e.VMID,
			Kind:     string(e.Kind),
		}
		if e.Err != nil {
			ev.Error = e.Err.Error()
		}
		out = append(out, ev)
	}
	jsonOK(w, out)
}

// handleActivityStream serves a Server-Sent Events stream of live activity.
func (s *Server) handleActivityStream(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "text/event-stream")
	w.Header().Set("Cache-Control", "no-cache")
	w.Header().Set("X-Accel-Buffering", "no")
	flusher, ok := w.(http.Flusher)
	if !ok {
		http.Error(w, "streaming not supported", http.StatusInternalServerError)
		return
	}

	fmt.Fprintf(w, "event: connected\ndata: {\"status\":\"streaming\"}\n\n")
	flusher.Flush()

	ch := s.sched.Events()
	for {
		select {
		case <-r.Context().Done():
			return
		case ev, open := <-ch:
			if !open {
				return
			}
			data, _ := json.Marshal(map[string]any{
				"time":     ev.Time.Format(time.RFC3339),
				"hostname": ev.Hostname,
				"vmid":     ev.VMID,
				"kind":     string(ev.Kind),
			})
			fmt.Fprintf(w, "event: activity\ndata: %s\n\n", data)
			flusher.Flush()
		}
	}
}

// --- helpers ----------------------------------------------------------------

func (s *Server) toView(p persona.Persona) personaView {
	v := personaView{
		Hostname:      p.Hostname,
		Character:     p.Character,
		SAM:           p.SAM,
		Domain:        p.ADDomain,
		Pace:          p.Pace,
		ActiveStart:   p.ActiveStart,
		ActiveEnd:     p.ActiveEnd,
		SignatureURLs: p.SignatureURLs,
	}
	if vm, ok := s.vmMap[p.Hostname]; ok {
		v.VMID = vm.VMID
		v.VMStatus = vm.Status
	}
	return v
}

// auth wraps a handler with optional Bearer token authentication.
func (s *Server) auth(next http.Handler) http.Handler {
	if s.token == "" {
		return next
	}
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		hdr := r.Header.Get("Authorization")
		if !strings.HasPrefix(hdr, "Bearer ") || strings.TrimPrefix(hdr, "Bearer ") != s.token {
			w.Header().Set("WWW-Authenticate", "Bearer")
			jsonErr(w, http.StatusUnauthorized, "invalid or missing bearer token")
			return
		}
		next.ServeHTTP(w, r)
	})
}

func jsonOK(w http.ResponseWriter, v any) {
	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(v)
}

func jsonErr(w http.ResponseWriter, code int, msg string) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(code)
	_ = json.NewEncoder(w).Encode(map[string]string{"error": msg})
}
