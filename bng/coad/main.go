// coad — CoA/DM daemon for the BNG
//
// Listens for RADIUS Change-of-Authorization (CoA) and Disconnect-Message (DM)
// requests on UDP :3799 (RFC 5176). Each request is forwarded to the BNG's
// Python event loop over a Unix domain socket for processing, and the result
// is sent back as a CoA-ACK/NAK or Disconnect-ACK/NAK.
//
// Environment variables:
//   RADIUS_SECRET    — shared secret with the AAA server (default: "testing123")
//   COA_LISTEN_ADDR  — UDP address to listen on (default: ":3799")
//   COA_IPC_SOCKET   — path to the Unix socket for BNG IPC (default: "/tmp/coad.sock")

package main

import (
	"fmt"
	"log"
	"os"

	"layeh.com/radius"
)

func main() {
	secret := envOrDefault("RADIUS_SECRET", "testing123")
	listenAddr := envOrDefault("COA_LISTEN_ADDR", ":3799")
	ipcSocket := envOrDefault("COA_IPC_SOCKET", "/tmp/coad.sock")

	log.Printf("coad starting  listen=%s  ipc=%s", listenAddr, ipcSocket)

	// Build the RADIUS packet handler
	handler := newCoAHandler(ipcSocket, []byte(secret))

	// Start the RADIUS CoA/DM server (blocks forever)
	server := radius.PacketServer{
		Addr:         listenAddr,
		Network:      "udp",
		SecretSource: radius.StaticSecretSource([]byte(secret)),
		Handler:      handler,
	}

	log.Fatal(server.ListenAndServe())
}

func envOrDefault(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	fmt.Printf("  %s not set, using default: %s\n", key, fallback)
	return fallback
}
