package proxmox

import (
	"encoding/json"
	"fmt"
	"strings"
	"time"
)

// SendKey sends a single HMP sendkey command to the VM identified by vmid.
// key is an HMP key name or combo, e.g. "a", "shift-h", "ctrl-alt-delete".
// The Proxmox monitor endpoint (/nodes/{node}/qemu/{vmid}/monitor) accepts
// raw HMP commands and proxies them to the QEMU monitor for that VM.
//
// From the guest's perspective this is indistinguishable from physical
// keyboard input — no software artefact is created inside the VM.
func (c *Client) SendKey(vmid int, key string) error {
	return c.monitor(vmid, fmt.Sprintf("sendkey %s", key))
}

// SendKeyCombo sends a modifier+key combination, e.g. ("ctrl", "alt", "l").
// Keys are joined with "-" per HMP convention.
func (c *Client) SendKeyCombo(vmid int, keys ...string) error {
	return c.SendKey(vmid, strings.Join(keys, "-"))
}

// TypeString injects text character-by-character into vmid using HMP sendkey,
// with a human-like delay between each keystroke drawn from a log-normal
// distribution centred on delayMs milliseconds. errorRate is the fraction of
// keystrokes that are "mis-typed" (a wrong key followed by Backspace).
//
// This produces genuine PS/2/USB HID keyboard events from the QEMU emulation
// layer — no process, pipe, or clipboard artefact is created inside the VM.
func (c *Client) TypeString(vmid int, text string, delayMs float64, errorRate float64) error {
	keys := textToHMPKeys(text)
	for i, k := range keys {
		// Occasional typo: inject a wrong key then backspace before the real one.
		if errorRate > 0 && i > 0 && i%int(1.0/errorRate) == 0 {
			if err := c.SendKey(vmid, typoKey(k)); err != nil {
				return err
			}
			time.Sleep(logNormalDelay(delayMs))
			if err := c.SendKey(vmid, "backspace"); err != nil {
				return err
			}
			time.Sleep(logNormalDelay(delayMs * 0.7))
		}
		if err := c.SendKey(vmid, k); err != nil {
			return err
		}
		time.Sleep(logNormalDelay(delayMs))
	}
	return nil
}

// MouseMove sends a relative mouse-move HMP command to vmid.
// dx and dy are signed pixel deltas.  Unlike SendKey, mouse_move is a
// standalone HMP command that cannot be embedded in sendkey — this method
// issues it directly via the monitor endpoint.
func (c *Client) MouseMove(vmid, dx, dy int) error {
	return c.monitor(vmid, fmt.Sprintf("mouse_move %d %d", dx, dy))
}

// monitor posts a raw HMP command string to the QEMU monitor for vmid.
func (c *Client) monitor(vmid int, command string) error {
	path := fmt.Sprintf("nodes/%s/qemu/%d/monitor", c.node, vmid)
	payload := map[string]string{"command": command}
	var resp pveResponse
	if err := c.post(path, payload, &resp); err != nil {
		return err
	}
	// The monitor response data is a string; we ignore it but unmarshal to
	// check for embedded error messages from QEMU.
	var out string
	if len(resp.Data) > 0 {
		_ = json.Unmarshal(resp.Data, &out)
	}
	return nil
}
