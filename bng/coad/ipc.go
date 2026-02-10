package main

import (
	"encoding/json"
	"fmt"
	"net"
	"time"
)

// IPCRequest is sent from coad to the Python BNG event loop.
type IPCRequest struct {
	Action    string `json:"action"`               // "disconnect" or "policy_change"
	SessionID string `json:"session_id"`            // RADIUS Acct-Session-Id
	FilterID  string `json:"filter_id,omitempty"`   // RADIUS Filter-Id (for policy_change)
}

// IPCResponse is received from the Python BNG event loop.
type IPCResponse struct {
	Success bool   `json:"success"`
	Error   string `json:"error,omitempty"`
}

const ipcTimeout = 3 * time.Second

// ipcRequest sends a request to the Python BNG event loop over a Unix socket
// and waits for the response. Each request opens a new connection — this keeps
// the protocol simple and avoids connection state management.
func ipcRequest(socketPath string, req IPCRequest) (*IPCResponse, error) {
	conn, err := net.DialTimeout("unix", socketPath, ipcTimeout)
	if err != nil {
		return nil, fmt.Errorf("connect to %s: %w", socketPath, err)
	}
	defer conn.Close()

	conn.SetDeadline(time.Now().Add(ipcTimeout))

	// Send JSON request
	if err := json.NewEncoder(conn).Encode(req); err != nil {
		return nil, fmt.Errorf("send request: %w", err)
	}

	// Read JSON response
	var resp IPCResponse
	if err := json.NewDecoder(conn).Decode(&resp); err != nil {
		return nil, fmt.Errorf("read response: %w", err)
	}

	return &resp, nil
}
