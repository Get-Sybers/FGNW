package proxmox

import (
	"encoding/json"
	"fmt"
	"strings"
)

// VMInfo is the subset of the PVE /qemu list entry we care about.
type VMInfo struct {
	VMID   int    `json:"vmid"`
	Name   string `json:"name"`
	Status string `json:"status"` // "running" | "stopped" | ...
}

// ListVMs returns all VMs on the configured node.
func (c *Client) ListVMs() ([]VMInfo, error) {
	var resp pveResponse
	if err := c.get(fmt.Sprintf("nodes/%s/qemu", c.node), &resp); err != nil {
		return nil, err
	}
	var vms []VMInfo
	if err := json.Unmarshal(resp.Data, &vms); err != nil {
		return nil, err
	}
	return vms, nil
}

// FindVMByName returns the VMInfo for a VM whose Name exactly matches name
// (case-insensitive).  Returns an error if not found or not running.
func (c *Client) FindVMByName(name string) (VMInfo, error) {
	vms, err := c.ListVMs()
	if err != nil {
		return VMInfo{}, err
	}
	lower := strings.ToLower(name)
	for _, vm := range vms {
		if strings.ToLower(vm.Name) == lower {
			return vm, nil
		}
	}
	return VMInfo{}, fmt.Errorf("VM %q not found on node %s", name, c.node)
}

// BuildVMMap returns a map of Ludus hostname → VMInfo for all names provided.
// Missing VMs are silently omitted from the result map; callers can compare
// len(result) vs len(names) to detect gaps.
func (c *Client) BuildVMMap(names []string) (map[string]VMInfo, error) {
	vms, err := c.ListVMs()
	if err != nil {
		return nil, err
	}
	// Build a lookup by lowercase name for O(1) access.
	byName := make(map[string]VMInfo, len(vms))
	for _, vm := range vms {
		byName[strings.ToLower(vm.Name)] = vm
	}
	result := make(map[string]VMInfo, len(names))
	for _, n := range names {
		if vm, ok := byName[strings.ToLower(n)]; ok {
			result[n] = vm
		}
	}
	return result, nil
}
