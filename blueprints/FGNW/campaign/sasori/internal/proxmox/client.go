// Package proxmox wraps the Proxmox VE REST API for the operations
// sasori needs: VM discovery, HMP sendkey (keyboard injection via the
// QEMU monitor), and QEMU Guest Agent exec (for high-level guest ops).
//
// All calls use a PVE API token (PVEAPIUser!TokenID=Secret) rather than
// password auth.  The token must carry at minimum:
//   - VM.Monitor on the relevant VMs (for /monitor — HMP sendkey)
//   - VM.Guest on the relevant VMs (for /agent/* — QGA exec)
//   - VM.Audit on the node (for /qemu list)
package proxmox

import (
	"bytes"
	"crypto/tls"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"time"
)

// Client is a thin Proxmox REST API client.
type Client struct {
	baseURL    string
	authHeader string // "PVEAPIToken=user@realm!id=secret"
	node       string
	http       *http.Client
}

// NewClient creates a Client.
// host should be the full base URL, e.g. "https://pve01:8006".
// insecure=true skips TLS verification (dev/self-signed only).
func NewClient(host, user, tokenID, secret, node string, insecure bool) *Client {
	tr := &http.Transport{
		TLSClientConfig: &tls.Config{InsecureSkipVerify: insecure},
	}
	return &Client{
		baseURL:    host,
		authHeader: fmt.Sprintf("PVEAPIToken=%s!%s=%s", user, tokenID, secret),
		node:       node,
		http:       &http.Client{Timeout: 15 * time.Second, Transport: tr},
	}
}

// Node returns the configured PVE node name.
func (c *Client) Node() string { return c.node }

// get performs a GET against path (relative to /api2/json/) and decodes JSON into dst.
func (c *Client) get(path string, dst interface{}) error {
	req, err := http.NewRequest(http.MethodGet, c.baseURL+"/api2/json/"+path, nil)
	if err != nil {
		return err
	}
	req.Header.Set("Authorization", c.authHeader)
	resp, err := c.http.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	body, _ := io.ReadAll(resp.Body)
	if resp.StatusCode >= 400 {
		return fmt.Errorf("GET %s: HTTP %d: %s", path, resp.StatusCode, body)
	}
	return json.Unmarshal(body, dst)
}

// post performs a POST with a JSON body against path and decodes the response into dst.
func (c *Client) post(path string, payload, dst interface{}) error {
	b, err := json.Marshal(payload)
	if err != nil {
		return err
	}
	req, err := http.NewRequest(http.MethodPost, c.baseURL+"/api2/json/"+path, bytes.NewReader(b))
	if err != nil {
		return err
	}
	req.Header.Set("Authorization", c.authHeader)
	req.Header.Set("Content-Type", "application/json")
	resp, err := c.http.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	body, _ := io.ReadAll(resp.Body)
	if resp.StatusCode >= 400 {
		return fmt.Errorf("POST %s: HTTP %d: %s", path, resp.StatusCode, body)
	}
	if dst != nil {
		return json.Unmarshal(body, dst)
	}
	return nil
}

// pveResponse wraps the top-level {"data": ...} envelope every PVE API call returns.
type pveResponse struct {
	Data json.RawMessage `json:"data"`
}
