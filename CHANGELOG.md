# Changelog

## 2026-02-09

### OSS Dashboard & Monitoring
- Added Next.js frontend with active sessions, session history, and events views
- Added FastAPI backend with read-only REST API (`/api/sessions/active`, `/api/sessions/history`, `/api/events`, `/api/routers`, `/api/bngs`, `/api/stats`)
- Added BNG health tracking — periodic CPU and memory reporting via `psutil`, persisted as time-series in `bng_health_events`
- Added passive access router discovery from DHCP Option 82 circuit-id, with per-router ICMP liveness checks and deferred pings on active DHCP traffic
- Added `access_routers` and `bng_registry` tables to the OSS schema
- Generated system architecture diagram (D2/dagre)

### Session Tracking Pipeline
- Completed end-to-end session event ingestion: BNG event dispatcher → Redis Stream (`bng_events`) → BNG Ingestor → OSS PostgreSQL
- Six event types: `SESSION_START`, `SESSION_UPDATE`, `SESSION_STOP`, `POLICY_APPLY`, `ROUTER_UPDATE`, `BNG_HEALTH_UPDATE`
- Sequence-based idempotency with `(bng_id, bng_instance_id, seq)` composite key
- Two-phase `SESSION_STOP`: update active session with final counters, then atomically move to `sessions_history` via `DELETE ... RETURNING` + `INSERT`
- Added `status` and `auth_state` columns to `sessions_active` and `sessions_history`

## 2026-02-06

### Event-Driven Architecture
- Introduced Redis container and `bng_events` stream with consumer group support
- Added BNG Ingestor service consuming from Redis and writing to OSS PostgreSQL
- Added OSS PostgreSQL container with `session_events`, `sessions_active`, `sessions_history` schema
- Implemented BNG Event Dispatcher with configurable test mode (stdout) and Redis mode
- Introduced `bng_id` and `bng_instance_id` for distributed BNG identity (replacing `nas_ip` as primary identifier)

## 2026-02-05

### Kea Migration & SR Linux Integration
- Migrated from dnsmasq to ISC Kea DHCPv4 with PostgreSQL-backed lease storage
- Rewrote BNG as a DHCP relay (raw `AF_PACKET` sockets) instead of a DHCP server
- Nokia SR Linux access switches fully working with DHCP relay and Option 82 injection
- Fixed DHCP RELEASE handling — no Option 82 present, resolved via IP-based session lookup
- Fixed aggregation switch dropping return packets from BNG
- Containerized all services with Docker Compose + Containerlab topology

## 2026-02-01 — 2026-02-03

### BNG Core Improvements
- Rewrote DHCP reply sniffing — upstream-facing raw socket captures server responses correctly
- Enhanced DHCP lease handling with proper IP change detection and accounting restart
- Added username formatting for RADIUS accounting (`relay_id/remote_id/circuit_id`)
- Improved IP validation and logging throughout the BNG event loop

## 2026-01-28

### RADIUS Authorization & Traffic Control
- Added RADIUS Access-Request/Accept/Reject flow with FreeRADIUS
- Built RADIUS packet builders for auth and accounting
- Default-deny traffic policy — subscribers blocked until RADIUS authorizes
- nftables `authed_ips` set for per-subscriber allow/deny

### Session Lifecycle
- Added tombstoning to prevent reconciler from re-creating intentionally stopped sessions
- Tombstones expire after TTL or when lease state advances

## 2026-01-25 — 2026-01-27

### Idle Detection & Threading
- Added idle session detection based on nftables counter deltas
- Idle sessions disconnected after configurable grace period
- Moved interim update loop to a separate thread
- Fixed race condition between interim-update and lease-handler threads
- Switched from polling DHCP lease file to watching for changes

## 2026-01-22 — 2026-01-23

### Initial BNG & Accounting
- Basic BNG workflow: DHCP lease parsing into subscriber sessions
- RADIUS Accounting (Start, Interim-Update, Stop)
- nftables per-subscriber traffic counters via `FORWARD` chain hooks on subscriber-facing interface
- Traffic byte/packet counters flowing into RADIUS accounting records

## 2026-01-21

### Project Init
- Initial project structure and Containerlab topology
- DHCP configuration (no DNS)
