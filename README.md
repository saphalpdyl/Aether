<img width="300" height="50" alt="image" src="https://github.com/user-attachments/assets/93d55429-403c-4694-8302-5119844b78c6" />
<br><br>

A full-stack ISP network lab that emulates broadband subscriber management end-to-end — from raw DHCP packet interception to real-time traffic dashboards. Built on an event-sourced architecture with RADIUS AAA, per-subscriber traffic shaping, passive network discovery, and traffic simulation, all orchestrated via Containerlab.

## Architecture

![System Architecture](docs/architecture.svg)

### Edge

Subscriber host containers acquire addresses via DHCP. Traffic passes through **DHCP relay agents** that inject Option 82 sub-options (circuit-id, remote-id, relay-id) before reaching the BNG through L2 aggregation bridges.

### BNG (Broadband Network Gateway)

Custom Python-based BNG, horizontally scalable to N instances. Each instance runs:

- **AF_PACKET Sniffer** — Raw socket capture on subscriber-facing interfaces for full DHCP relay control and Option 82 rewriting.
- **Async Event Loop** — Single-writer loop with priority queue multiplexing DHCP events and periodic maintenance commands (reconcile, interim accounting, auth retry, health checks).
- **Session Manager** — Per-subscriber lifecycle management with three data-plane integrations:
  - **nftables** — Per-session upload/download byte counters without userspace packet copies.
  - **TC/HTB Shaper** — Hierarchical token bucket traffic shaping derived from RADIUS speed AVPs.
  - **Event Dispatcher** — Produces sequenced, idempotent events to the event bus.
- **Health Tracker** — Per-container CPU and memory metrics via cgroup v2/v1 files.

### Network Services

- **Kea DHCP** — ISC Kea DHCPv4 with PostgreSQL lease storage and a control agent API (`:6772`) used for periodic lease reconciliation.
- **FreeRADIUS** — Auth (`:1812`) and Accounting (`:1813`) with PostgreSQL-backed user profiles. Supports CoA Disconnect-Request for admin-initiated session termination.

### Event Pipeline

Session lifecycle events flow from the BNG's event dispatcher into a **Redis Stream** (`bng_events`), consumed by an ingestor via consumer groups for reliable, at-least-once delivery with sequence-based idempotency.

| Event | Trigger |
|---|---|
| `SESSION_START` | DHCP ACK with new IP assignment |
| `SESSION_UPDATE` | Periodic interim accounting update |
| `SESSION_STOP` | DHCP RELEASE, lease expiry, idle timeout, or IP change |
| `POLICY_APPLY` | RADIUS Access-Accept or Reject received |
| `ROUTER_UPDATE` | Access router discovered or health state change |
| `BNG_HEALTH_UPDATE` | Periodic CPU/memory utilization report |

### Storage

Three domain-separated PostgreSQL instances:

- **OSS PG** — `session_events` (immutable log, keyed by `bng_id, instance_id, seq`), `sessions_active` (live sessions with traffic counters), `sessions_history` (archived with GiST time-range indexes), `access_routers`, `bng_registry`, `bng_health_events`, `customers`, `plans`, `services`.
- **DHCP PG** — `lease4` (Kea lease storage).
- **RADIUS PG** — `radacct`, `radcheck`, `radreply`, `radusergroup`.

### Presentation

- **Backend** — FastAPI service with dual PostgreSQL connection pools (OSS + RADIUS) serving REST endpoints for sessions, events, routers, BNG health, customers, plans, services, and traffic time-series.
- **Frontend** — Next.js dashboard with:
  - **OSS Dashboard** — Real-time session monitoring with live traffic metrics (5-minute rolling average), active sessions table with expandable customer details, BNG health cards with CPU/memory graphs, aggregate traffic analytics, and session history/events tabs.
  - **Provisioning Console** — Customer relationship management with service provisioning, plan assignment, and RADIUS profile synchronization.

### Simulator

A Docker-socket-attached container that drives the lab:

1. **Service Provisioning** — Creates customer-to-plan service bindings via the backend API, which syncs to RADIUS user profiles.
2. **DHCP Acquisition** — Triggers `dhclient` on each host container with retry logic.
3. **Traffic Generation** — Spawns per-host daemon threads running weighted random commands (curl, dig, iperf3) from a JSON config with configurable sleep ranges.

## Design Decisions

**Event sourcing with sequence-based idempotency** — Each BNG instance maintains a monotonic sequence counter. The composite key `(bng_id, bng_instance_id, seq)` in `session_events` guarantees exactly-once semantics at the persistence layer, even with at-least-once stream delivery. Events are the source of truth; read models are derived.

**Two-phase session stop** — `SESSION_STOP` updates the active session with final traffic counters, then atomically moves it to history via `DELETE ... RETURNING` + `INSERT`, preventing data loss during the transition.

**5-minute rolling traffic average** — Active Traffic card displays bandwidth rates calculated over a 5-minute window rather than instantaneous 2-second deltas, providing smoother metrics and preventing "0 bps" display during brief idle periods.

**Reconciliation loop** — A periodic reconciler queries Kea's control agent for authoritative lease state, recovering missed sessions after BNG restarts. TTL-based tombstones prevent the reconciler from re-creating intentionally terminated sessions.

**Raw socket DHCP relay** — The BNG intercepts DHCP at the packet level via `AF_PACKET` rather than using a kernel relay, giving full control over Option 82 manipulation and enabling session creation at the moment of DHCP exchange.

## Tech Stack

| Layer | Technology |
|---|---|
| Network Emulation | Containerlab |
| BNG Core | Python, asyncio, raw sockets (`AF_PACKET`), nftables, `tc`/HTB |
| DHCP | ISC Kea, PostgreSQL |
| AAA | FreeRADIUS, PostgreSQL |
| Event Bus | Redis Streams (consumer groups) |
| Persistence | PostgreSQL (3 instances) |
| Backend | FastAPI, psycopg2 |
| Frontend | Next.js 15, React, TanStack Table, Recharts, Tailwind CSS |
| Simulator | Python, Docker SDK |

## Network Topology
This is the network topology for a standard two-BNG configuration.
![System Architecture](docs/network_topology.svg)

## Screenshots

<img width="2481" height="1418" alt="image" src="https://github.com/user-attachments/assets/1d14f888-fd88-4baa-bf61-2e69e29fd0e3" />
<img width="2471" height="1410" alt="image" src="https://github.com/user-attachments/assets/57881cb0-6a13-45f0-b2c9-b588ac27a508" />
<img width="2481" height="1434" alt="image" src="https://github.com/user-attachments/assets/0aff4905-93d8-4a59-88ca-ec854803d654" />
