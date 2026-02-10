package main

import (
	"log"

	"layeh.com/radius"
	"layeh.com/radius/rfc2865"
	"layeh.com/radius/rfc2866"
)

// coaHandler implements radius.Handler.
// It extracts session identity from incoming CoA/DM packets and delegates
// the actual work to the Python BNG event loop over IPC.
type coaHandler struct {
	ipcSocket string
	secret    []byte
}

func newCoAHandler(ipcSocket string, secret []byte) *coaHandler {
	return &coaHandler{
		ipcSocket: ipcSocket,
		secret:    secret,
	}
}

func (h *coaHandler) ServeRADIUS(w radius.ResponseWriter, r *radius.Request) {
	switch r.Code {

	case radius.CodeDisconnectRequest:
		h.handleDisconnect(w, r)

	case radius.CodeCoARequest:
		h.handleCoA(w, r)

	default:
		log.Printf("ignoring unknown RADIUS code: %d", r.Code)
	}
}

// handleDisconnect processes a Disconnect-Request (RFC 5176).
// The OSS sends this when it wants to terminate a subscriber session.
func (h *coaHandler) handleDisconnect(w radius.ResponseWriter, r *radius.Request) {
	sessionID := rfc2866.AcctSessionID_GetString(r.Packet)
	username := rfc2865.UserName_GetString(r.Packet)

	log.Printf("disconnect-request  session_id=%s  username=%s", sessionID, username)

	if sessionID == "" {
		log.Printf("disconnect-request rejected: missing Acct-Session-Id")
		writeResponse(w, r, radius.CodeDisconnectNAK)
		return
	}

	result, err := ipcRequest(h.ipcSocket, IPCRequest{
		Action:    "disconnect",
		SessionID: sessionID,
	})

	if err != nil {
		log.Printf("disconnect ipc error: %v", err)
		writeResponse(w, r, radius.CodeDisconnectNAK)
		return
	}

	if !result.Success {
		log.Printf("disconnect rejected: %s", result.Error)
		writeResponse(w, r, radius.CodeDisconnectNAK)
		return
	}

	log.Printf("disconnect-ack  session_id=%s", sessionID)
	writeResponse(w, r, radius.CodeDisconnectACK)
}

// handleCoA processes a CoA-Request (RFC 5176).
// The OSS sends this to change a subscriber's policy (e.g., rate limit, plan tier).
func (h *coaHandler) handleCoA(w radius.ResponseWriter, r *radius.Request) {
	sessionID := rfc2866.AcctSessionID_GetString(r.Packet)
	filterID := rfc2865.FilterID_GetString(r.Packet)
	username := rfc2865.UserName_GetString(r.Packet)

	log.Printf("coa-request  session_id=%s  filter_id=%s  username=%s", sessionID, filterID, username)

	if sessionID == "" {
		log.Printf("coa-request rejected: missing Acct-Session-Id")
		writeResponse(w, r, radius.CodeCoANAK)
		return
	}

	result, err := ipcRequest(h.ipcSocket, IPCRequest{
		Action:    "policy_change",
		SessionID: sessionID,
		FilterID:  filterID,
	})

	if err != nil {
		log.Printf("coa ipc error: %v", err)
		writeResponse(w, r, radius.CodeCoANAK)
		return
	}

	if !result.Success {
		log.Printf("coa rejected: %s", result.Error)
		writeResponse(w, r, radius.CodeCoANAK)
		return
	}

	log.Printf("coa-ack  session_id=%s  filter_id=%s", sessionID, filterID)
	writeResponse(w, r, radius.CodeCoAACK)
}

func writeResponse(w radius.ResponseWriter, r *radius.Request, code radius.Code) {
	w.Write(r.Response(code))
}
