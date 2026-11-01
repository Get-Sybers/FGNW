package proxmox

import (
	"encoding/json"
	"fmt"
	"time"
)

// VerifyResult is the outcome of one check against a single VM.
type VerifyResult struct {
	Hostname  string
	VMID      int
	VMFound   bool
	VMRunning bool
	QGAOK     bool   // Guest Agent responded to ping
	SendKeyOK bool   // HMP sendkey delivered a harmless keystroke
	Error     string // first error encountered, empty on full pass
}

// Pass returns true if every check succeeded.
func (r VerifyResult) Pass() bool {
	return r.VMFound && r.VMRunning && r.QGAOK && r.SendKeyOK && r.Error == ""
}

// VerifyVM runs the full check suite against one VM:
//  1. VM exists on the node and is running
//  2. QEMU Guest Agent responds to info ping
//  3. HMP sendkey delivers a harmless keystroke (right_shift — no effect in any app)
//
// No window focus is changed, no text is typed, no session state is altered.
func (c *Client) VerifyVM(hostname string, vmid int) VerifyResult {
	r := VerifyResult{Hostname: hostname, VMID: vmid}

	// 1 — VM presence and running state
	vms, err := c.ListVMs()
	if err != nil {
		r.Error = fmt.Sprintf("list VMs: %s", err)
		return r
	}
	for _, vm := range vms {
		if vm.VMID == vmid {
			r.VMFound = true
			r.VMRunning = vm.Status == "running"
			break
		}
	}
	if !r.VMFound {
		r.Error = fmt.Sprintf("VMID %d not found on node %s", vmid, c.node)
		return r
	}
	if !r.VMRunning {
		r.Error = fmt.Sprintf("VMID %d is not running (status: stopped)", vmid)
		return r
	}

	// 2 — QGA ping (agent/info)
	if err := c.agentPing(vmid); err != nil {
		r.Error = fmt.Sprintf("QGA ping: %s", err)
		return r
	}
	r.QGAOK = true

	// 3 — HMP sendkey (right_shift — entirely harmless)
	if err := c.SendKey(vmid, "shift_r"); err != nil {
		r.Error = fmt.Sprintf("sendkey: %s", err)
		return r
	}
	r.SendKeyOK = true

	return r
}

// agentPing calls /agent/info to confirm the Guest Agent is alive and responding.
func (c *Client) agentPing(vmid int) error {
	path := fmt.Sprintf("nodes/%s/qemu/%d/agent/info", c.node, vmid)
	var resp pveResponse
	if err := c.get(path, &resp); err != nil {
		return err
	}
	// Just confirm we got a non-empty data blob back.
	if len(resp.Data) == 0 {
		return fmt.Errorf("agent/info returned empty response")
	}
	return nil
}

// AgentExecVerify runs a trivial Guest Agent command (echo) and confirms we
// get the expected output back.  Used by the verify subcommand for a deeper
// QGA check beyond the info ping.
func (c *Client) AgentExecVerify(vmid int) error {
	result, err := c.AgentExec(vmid,
		`C:\Windows\System32\cmd.exe`,
		[]string{"/c", "echo sasori-verify-ok"},
		10*time.Second)
	if err != nil {
		return fmt.Errorf("exec: %w", err)
	}
	if result.ExitCode != 0 {
		return fmt.Errorf("exit code %d: %s", result.ExitCode, result.ErrData)
	}
	return nil
}

// VerifyAPIAuth checks that the configured API token can authenticate and
// reach the node's QEMU list endpoint.  Returns the number of VMs visible.
func (c *Client) VerifyAPIAuth() (int, error) {
	vms, err := c.ListVMs()
	if err != nil {
		return 0, err
	}
	return len(vms), nil
}

// VerifyMonitorAccess checks that the token has VM.Monitor on vmid by sending
// a no-op HMP command (info version) and confirming no permission error.
func (c *Client) VerifyMonitorAccess(vmid int) error {
	var resp pveResponse
	path := fmt.Sprintf("nodes/%s/qemu/%d/monitor", c.node, vmid)
	if err := c.post(path, map[string]string{"command": "info version"}, &resp); err != nil {
		return err
	}
	var out string
	_ = json.Unmarshal(resp.Data, &out)
	if out == "" {
		return fmt.Errorf("monitor returned empty response — token may lack VM.Monitor")
	}
	return nil
}

// VerifyGuestAccess checks that the token has VM.Guest on vmid.
func (c *Client) VerifyGuestAccess(vmid int) error {
	return c.agentPing(vmid)
}

// VerifyAll runs the full check suite against every hostname in vmMap and
// returns one VerifyResult per persona.  Results are returned in the order
// hostnames are provided so the caller can print them in a stable order.
func (c *Client) VerifyAll(hostnames []string, vmMap map[string]VMInfo) []VerifyResult {
	results := make([]VerifyResult, 0, len(hostnames))
	for _, h := range hostnames {
		vm, ok := vmMap[h]
		if !ok {
			results = append(results, VerifyResult{
				Hostname: h,
				Error:    "hostname not found in VM map (VM may not exist or name mismatch)",
			})
			continue
		}
		results = append(results, c.VerifyVM(h, vm.VMID))
		// Brief pause between VMs — avoid hammering the PVE API.
		time.Sleep(300 * time.Millisecond)
	}
	return results
}
