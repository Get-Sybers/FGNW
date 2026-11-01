package proxmox

import (
	"encoding/json"
	"fmt"
	"time"
)

// AgentExecResult holds the stdout/stderr/exit-code of a Guest Agent exec call.
type AgentExecResult struct {
	ExitCode int    `json:"exitcode"`
	OutData  string `json:"out-data"`
	ErrData  string `json:"err-data"`
	Exited   bool   `json:"exited"`
}

// AgentExec runs a command inside the VM via the QEMU Guest Agent.
// cmd is the executable path; args are its arguments.
// The call blocks until the guest reports the process has exited (polling
// every pollInterval) or timeout elapses.
//
// This runs as SYSTEM on Windows VMs.  Use it for operations that need an
// OS-level result (reading a registry key, checking which user is logged in,
// file copy) rather than for simulated user input — that goes through SendKey.
func (c *Client) AgentExec(vmid int, cmd string, args []string, timeout time.Duration) (AgentExecResult, error) {
	// Start the process.
	type execReq struct {
		Command          string   `json:"command"`
		Args             []string `json:"args,omitempty"`
		CaptureOutput    bool     `json:"capture-output"`
	}
	type pidResp struct {
		PID int `json:"pid"`
	}
	path := fmt.Sprintf("nodes/%s/qemu/%d/agent/exec", c.node, vmid)
	var startResp pveResponse
	if err := c.post(path, execReq{Command: cmd, Args: args, CaptureOutput: true}, &startResp); err != nil {
		return AgentExecResult{}, fmt.Errorf("agent exec start: %w", err)
	}
	var pid pidResp
	if err := json.Unmarshal(startResp.Data, &pid); err != nil {
		return AgentExecResult{}, fmt.Errorf("agent exec pid decode: %w", err)
	}

	// Poll for completion.
	deadline := time.Now().Add(timeout)
	statusPath := fmt.Sprintf("nodes/%s/qemu/%d/agent/exec-status?pid=%d", c.node, vmid, pid.PID)
	for time.Now().Before(deadline) {
		time.Sleep(500 * time.Millisecond)
		var statusResp pveResponse
		if err := c.get(statusPath, &statusResp); err != nil {
			return AgentExecResult{}, fmt.Errorf("agent exec status: %w", err)
		}
		var result AgentExecResult
		if err := json.Unmarshal(statusResp.Data, &result); err != nil {
			return AgentExecResult{}, err
		}
		if result.Exited {
			return result, nil
		}
	}
	return AgentExecResult{}, fmt.Errorf("agent exec timed out after %s (pid %d)", timeout, pid.PID)
}

// AgentLoggedOnUser returns the sAMAccountName of the interactively logged-on
// user, or "" if no session is active.  Uses quser.exe via the Guest Agent.
func (c *Client) AgentLoggedOnUser(vmid int) (string, error) {
	result, err := c.AgentExec(vmid,
		`C:\Windows\System32\quser.exe`, nil, 10*time.Second)
	if err != nil {
		return "", err
	}
	// quser.exe output includes a header line then one row per session.
	// We just need to know if anyone is logged on; parse the first non-header line.
	if result.ExitCode != 0 || result.OutData == "" {
		return "", nil // no active sessions
	}
	// Very rough parse: first token after the header is the username.
	lines := splitLines(result.OutData)
	for _, line := range lines[1:] {
		fields := fields(line)
		if len(fields) > 0 {
			return fields[0], nil
		}
	}
	return "", nil
}

// AgentFileWrite writes content to a file inside the guest via the QGA
// guest-file-* protocol (open → write → close).
func (c *Client) AgentFileWrite(vmid int, guestPath, content string) error {
	type openReq struct {
		File string `json:"path"`
		Mode string `json:"mode"`
	}
	type handleResp struct {
		Handle int `json:"handle"`
	}
	openPath := fmt.Sprintf("nodes/%s/qemu/%d/agent/file-write", c.node, vmid)

	// Use guest-exec to write via PowerShell — simpler than the raw QGA file
	// protocol over the Proxmox REST API (the raw protocol needs base64 + chunking
	// but the /agent/file-write endpoint is not exposed in all PVE versions).
	psCmd := fmt.Sprintf(
		`[System.IO.File]::WriteAllText('%s', '%s', [System.Text.Encoding]::UTF8)`,
		guestPath, escapePSString(content))
	_, err := c.AgentExec(vmid,
		`C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe`,
		[]string{"-NoProfile", "-NonInteractive", "-Command", psCmd},
		15*time.Second)
	_ = openPath // path used for documentation reference only in this impl
	return err
}

// --- helpers ----------------------------------------------------------------

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

func fields(s string) []string {
	var out []string
	inWord := false
	start := 0
	for i, r := range s {
		if r == ' ' || r == '\t' {
			if inWord {
				out = append(out, s[start:i])
				inWord = false
			}
		} else {
			if !inWord {
				start = i
				inWord = true
			}
		}
	}
	if inWord {
		out = append(out, s[start:])
	}
	return out
}

func escapePSString(s string) string {
	out := ""
	for _, r := range s {
		if r == '\'' {
			out += "''"
		} else {
			out += string(r)
		}
	}
	return out
}
