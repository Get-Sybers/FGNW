// Package ghosts provides a thin client for posting sasori activity events
// to a GHOSTS 9 API server.  All operations are best-effort — failures are
// returned to the caller to log, but never block emulation.
//
// # GHOSTS 9.3.0 REST API contract assumed here
//
//	GET  /api/machines          → [{id, name, fqdn, ...}, ...]
//	POST /api/clientresults     ← {machineId, type, success, output, executionTime}
//
// The client resolves hostname → GHOSTS machine GUID on first use, then caches
// the result for the session.  If a machine has never called home to GHOSTS
// (its GUID is not in the database), the call is skipped and an error returned.
package ghosts

import (
	"bytes"
	"encoding/json"
	"fmt"
	"net/http"
	"sync"
	"time"
)

// Client posts sasori activity to a GHOSTS 9 API server.
type Client struct {
	baseURL    string
	httpClient *http.Client

	mu       sync.RWMutex
	machines map[string]string // lowercase hostname → GUID
	loaded   bool
}

// New creates a Client targeting the given GHOSTS API base URL.
// The URL should include the /api path prefix, e.g. "http://10.2.99.51:5000/api".
func New(baseURL string) *Client {
	return &Client{
		baseURL: baseURL,
		httpClient: &http.Client{
			Timeout: 5 * time.Second,
		},
		machines: make(map[string]string),
	}
}

// ghostsMachine is one entry from GET /api/machines.
type ghostsMachine struct {
	ID   string `json:"id"`
	Name string `json:"name"`
	FQDN string `json:"fqdn"`
}

// clientResult is the POST /api/clientresults body.
type clientResult struct {
	MachineID     string    `json:"machineId"`
	Type          string    `json:"type"`
	Success       bool      `json:"success"`
	Output        string    `json:"output"`
	ExecutionTime time.Time `json:"executionTime"`
}

// loadMachines fetches the full machine list from GHOSTS and populates the
// hostname → GUID cache.  Safe to call concurrently.
func (c *Client) loadMachines() error {
	resp, err := c.httpClient.Get(c.baseURL + "/machines")
	if err != nil {
		return fmt.Errorf("GET /machines: %w", err)
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("GET /machines: status %d", resp.StatusCode)
	}
	var machines []ghostsMachine
	if err := json.NewDecoder(resp.Body).Decode(&machines); err != nil {
		return fmt.Errorf("decode machines: %w", err)
	}
	c.mu.Lock()
	for _, m := range machines {
		if m.Name != "" {
			c.machines[m.Name] = m.ID
		}
		if m.FQDN != "" {
			c.machines[m.FQDN] = m.ID
		}
	}
	c.loaded = true
	c.mu.Unlock()
	return nil
}

// machineID returns the GHOSTS GUID for hostname, loading the machine list on
// the first call.  Returns an error if the hostname has no registration.
func (c *Client) machineID(hostname string) (string, error) {
	c.mu.RLock()
	id, ok := c.machines[hostname]
	loaded := c.loaded
	c.mu.RUnlock()

	if ok {
		return id, nil
	}
	if !loaded {
		if err := c.loadMachines(); err != nil {
			return "", err
		}
		c.mu.RLock()
		id, ok = c.machines[hostname]
		c.mu.RUnlock()
		if ok {
			return id, nil
		}
	}
	return "", fmt.Errorf("machine %q not registered in GHOSTS (has not called home yet)", hostname)
}

// ReportActivity posts one sasori activity event to the GHOSTS API on behalf
// of hostname.  activityKind is one of the activity.Kind string values; it is
// mapped to a GHOSTS handler type.  note carries a human-readable description.
func (c *Client) ReportActivity(hostname, activityKind string, success bool, note string) error {
	id, err := c.machineID(hostname)
	if err != nil {
		return err
	}
	result := clientResult{
		MachineID:     id,
		Type:          toGHOSTSType(activityKind),
		Success:       success,
		Output:        note,
		ExecutionTime: time.Now().UTC(),
	}
	body, err := json.Marshal(result)
	if err != nil {
		return fmt.Errorf("marshal: %w", err)
	}
	resp, err := c.httpClient.Post(c.baseURL+"/clientresults", "application/json", bytes.NewReader(body))
	if err != nil {
		return fmt.Errorf("POST /clientresults: %w", err)
	}
	defer resp.Body.Close()
	if resp.StatusCode >= 400 {
		return fmt.Errorf("POST /clientresults: status %d", resp.StatusCode)
	}
	return nil
}

// toGHOSTSType maps a sasori activity.Kind string to a GHOSTS handler type.
// GHOSTS uses these to categorise timeline entries in its dashboard.
func toGHOSTSType(kind string) string {
	switch kind {
	case "type":
		return "Notepad"
	case "open_file":
		return "Execute"
	case "lock", "unlock", "logoff":
		return "Keepalive"
	default:
		return "Keepalive"
	}
}
