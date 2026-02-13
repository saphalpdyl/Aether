# Roadmap

## In Progress
- **Alerting** — Notify on router down, BNG health degradation, or session anomalies
- **Historical analytics** — Per-subscriber traffic trends, peak usage hours, session duration distributions

## Planned

- **Multi-BNG support** — Test and harden the event pipeline for multiple BNG instances reporting to the same OSS
- **Timer-wheel session scheduler** — Introduce per-session timer-wheel based scheduling in the BNG runtime for lease/reconcile/auth-retry/interim/idle-disconnect deadlines. Keep a single-writer state machine and route timer expirations as prioritized commands to avoid shared-state races while maintaining deterministic timing under load.
- **Development setup documentation** — Contributor-friendly setup guide with Containerlab prerequisites and build instructions

## Future

- **Declarative topology generation** — Define the entire distributed BNG deployment in a single YAML file: number of BNG instances, IP allocations, access router assignments, DHCP pools, RADIUS targets, and subscriber density per node. A Jinja2 templating engine generates the full Containerlab topology, SR Linux configs, Kea subnets, and BNG environment variables from this single source of truth. Spin up a 1-BNG lab or a 10-BNG mesh with one config change.
- **Distributed BNG system** — Multiple BNG instances operating as a coordinated cluster, each owning a slice of the access network. Session state replicated across instances via Redis for sub-second failover. Centralized OSS aggregates events from all BNGs with per-instance health tracking already in place. VRRP on gateway IPs for transparent subscriber failover.
- **Traffic intelligence** — Classify subscriber traffic by protocol at the data plane layer. Identify DNS, HTTP, TLS (via SNI), QUIC, and streaming protocols from packet headers. Tag flows and export per-subscriber traffic breakdowns (streaming, gaming, web, other) to the OSS for visualization on the dashboard. Enables usage-based insights without full DPI.
- **Lab simulation UI** — A non-traditional operator interface purpose-built for the lab environment. Instead of mimicking a production NOC dashboard, exposes direct control over subscriber hosts through Containerlab's Docker bridge. Demo users can simulate real subscriber behavior — trigger DHCP discover/release, bring interfaces up/down, and watch sessions appear and tear down in real time — all from the browser without touching a terminal.
- **XDP/eBPF data plane** — Replace the current raw socket DHCP relay and nftables accounting with an XDP program for line-rate packet processing. DHCP packets redirected to userspace via `AF_XDP` sockets, per-subscriber traffic counters maintained in eBPF maps, and policy enforcement (allow/deny/rate-limit) applied in the kernel before packets ever reach the network stack.

## Done

- BNG core with raw socket DHCP relay and Option 82 handling
- RADIUS AAA (Access-Request, Accounting Start/Interim/Stop)
- Per-subscriber nftables traffic accounting
- Event-driven session pipeline (Redis Streams → PostgreSQL)
- Passive access router discovery with ICMP health checks
- BNG health monitoring (CPU, memory)
- FastAPI read-only dashboard API
- Next.js frontend
- Apply per-subscriber bandwidth policies through nftables or tc based on RADIUS Filter-Id attributes pushed via CoA
- Go-based RADIUS Change-of-Authorization and Disconnect-Message daemon running alongside the BNG. Communicates with the Python event loop over Unix socket IPC. Enables the OSS to dynamically disconnect subscribers or change policies in real time.