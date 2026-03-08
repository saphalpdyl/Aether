# Aether BNG Performance Investigation - Blog Post Notes

## Background
- Aether is a Python-based BNG (Broadband Network Gateway) ISP simulation
- Deployed on Hetzner, running on a $6/mo shared 4 vCPU node
- Architecture: Python control plane (DHCP/RADIUS/session management) + nftables data plane
- Topology: host containers → cstm-relay → agg-bng → bng-01/02 → upstream
- All containers run via Containerlab on a single Hetzner node

## Initial Hypothesis (Wrong)
- Assumed Python userspace overhead was the bottleneck
- Assumed 700 Mbps ceiling was a software limitation
- Assumed both BNGs were saturating independently

## Investigation Step 1: Monitoring Bug
- Both BNG dashboards showed identical CPU/memory metrics (89.4%, 21.8%)
- Root cause: containers were reading `/proc/stat` which reports host-wide stats
- Both containers share root cgroup (`0::/`) so no cgroup isolation for metrics
- Fix: read from `/sys/fs/cgroup/cpu.stat` instead of `/proc/stat`
- `usage_usec` is a cumulative counter — must sample twice to calculate rate
- Better approach: store last seen `usage_usec` and diff against elapsed time
- Memory fix: read from `/sys/fs/cgroup/memory.current` for per-container usage
- Result: bng-01 showing 14.2% vs bng-02 showing 17.1% — genuinely different

## Investigation Step 2: The 700 Mbps Ceiling
- Initial iperf3 test: 700 Mbps on Hetzner with 3 streams, 10 seconds
- Hypothesis: Python/nftables bottleneck
- Local test with 2 Gbps plan limit: **1.31 Gbps sustained, only 38 retransmits**
- Conclusion: 700 Mbps was Hetzner shared vCPU ceiling, not software

## Investigation Step 3: Real Bottleneck Found
- Local test with 2 Gbps limit but simulated subscribers active: **206 Mbps, 4104 retransmits**
- 6x throughput collapse under 17 subscribers
- Only 17 active sessions caused this collapse

## perf top Analysis (During iperf3 Test)
First run showed:
```
27.16% [kernel] nft_do_chain
11.39% [kernel] nft_meta_get_eval
```
nftables consuming ~38% of CPU samples. Kernel at 74.2% total.

Second more detailed run (242K samples):
```
3.06%  nft_do_chain
2.11%  rep_movs_alternative
1.25%  nft_meta_get_eval
0.92%  __raw_spin_lock_irqsave
0.91%  skb_datagram_iter
0.90%  memset_orig
0.90%  kmem_cache_free
0.79%  __netif_receive_skb
0.64%  packet_rcv          ← relay_switch raw socket
```

With PID attribution:
```
2.06%  iperf3   nft_do_chain      ← BNG subscriber rules
0.89%  iperf3   nft_meta_get_eval
0.28%  ksoftirqd/3  nft_do_chain  ← all 4 CPU cores saturated
0.25%  ksoftirqd/2  nft_do_chain
0.22%  ksoftirqd/0  nft_do_chain
0.21%  ksoftirqd/1  nft_do_chain
```

## CPU Cost Per Throughput
| Plan | Actual Throughput | CPU Usage | Cost |
|------|------------------|-----------|------|
| 100 Mbps | 116 Mbps | 140% | ~1.2% per Mbps |
| 2 Gbps | 994 Mbps | 309% | ~0.3% per Mbps |

At 994 Mbps: **3 full CPU cores consumed for a single subscriber**

## nftables Rule Count
- BNG: 150 lines total (~9 rules per subscriber for 17 subscribers)
- Relay: 21 lines (drop rules for DHCP packet duplication prevention)
- Host containers: Docker embedded DNS NAT rules (hidden, installed automatically)

## relay_switch Architecture
- Pure Python raw socket DHCP interceptor
- Only processes UDP 67/68 — DHCP packets only
- Regular data traffic (iperf3, curl) flows through kernel routing normally
- Raw socket receives ALL packets via copy, Python ignores non-DHCP
- `packet_rcv` at 0.64% in perf top = raw socket copying every packet to userspace
- Fix: `SO_ATTACH_FILTER` with cBPF filter for UDP 67/68 only
- But: DHCP is low frequency during steady state, optimization impact minimal

## Veth Stack Overhead Analysis
Every packet crossing a veth pair pays:
- `veth_xmit` — transmit processing
- `skb_clone` — buffer copy
- `kmem_cache_alloc/free` — memory allocation
- `__netif_receive_skb` — packet receive processing
- `__raw_spin_lock` — locking
- routing table lookup
- neighbour lookup

Packet path: `host → relay → agg → bng → upstream` = 4 veth crossings

Aggregate veth overhead from perf top: ~7-8% of samples vs nftables ~4%
Absolute CPU: veth ~23% vs nftables ~13%

**Veth overhead is the dominant cost, nftables is secondary.**

## bpftrace Investigation
Traced `nft_do_chain` per network namespace:
```
4026537164 (h-cstm-relay-02-eth1): 1,609,515  ← appeared to be massive
4026531840 (host netns):             345,877
4026536962 (upstream):                93,817
4026533386 (bng-01):                  36,553
```

Investigation of h-cstm-relay-02-eth1 (traffic source):
- Only 1 nft ruleset line — essentially no rules
- But Docker installs hidden embedded DNS NAT rules in every container netns:
```
table ip nat {
    chain OUTPUT { type nat hook output priority dstnat; }      ← fires every packet
    chain POSTROUTING { type nat hook postrouting priority srcnat; } ← fires every packet
}
```
- These chains fire for every packet but immediately fail the `127.0.0.11` check
- 1,609,515 calls ÷ ~722,000 packets ≈ 2.2 (exactly 2 chains per packet)
- **Red herring** — trivial no-op evaluations, negligible CPU cost

## veth bpftrace Results
```
veth_xmit top contributors:
h-cstm-relay-02-eth1:  3,093,890  (TCP ACKs for download test)
host netns:              864,937
upstream:                148,192
bng-01:                   29,108
cstm-relay-01:            28,811

skb_clone top contributors:
h-cstm-relay-02-eth1:  2,805,187
host netns:            1,175,688
upstream:                166,394
bng-01:                   36,250
cstm-relay-01:            35,629
```

## Environment Comparison
| Environment | Throughput | Retransmits | Notes |
|-------------|-----------|-------------|-------|
| Local VM (4 vCPU dedicated) | 1.31 Gbps | 38 | Clean baseline |
| Hetzner shared (idle) | ~700 Mbps | low | Network ceiling |
| Hetzner shared (17 subscribers) | 206 Mbps | 4104 | CPU starvation |
| Hetzner shared (hosted test) | 477 Mbps | 1461 | Noisy neighbor |

## Root Cause Summary
1. **Hetzner shared vCPU ceiling** — explains 700 Mbps vs 1.31 Gbps local
2. **veth stack traversal** — dominant overhead, ~23% absolute CPU, distributed across all hops
3. **nftables subscriber rules** — secondary overhead, ~13% absolute CPU, all 4 ksoftirqd threads saturated
4. **Docker embedded DNS** — red herring, high call count but negligible cost
5. **Noisy neighbor contention** — causes packet drops → TCP retransmits → throughput collapse

## Proposed Optimizations (Not Yet Implemented)

### 1. TC eBPF redirect (biggest win)
- Replace veth stack traversal with `bpf_redirect_peer()`
- Eliminates: routing lookup, neighbour lookup, skb_clone, kmem_alloc, veth_xmit at each hop
- What you lose: netfilter hooks, TTL decrement, conntrack, ICMP generation
- For fixed Containerlab topology: acceptable tradeoffs
- Cilium's approach: replace all lost functionality with eBPF equivalents (months of work)
- Practical scope: TC eBPF on internal ISP network only (relay → agg → bng)
- Incoming packets need IP→ifindex hashmap for per-subscriber routing
- Control plane challenge: BNG needs to update relay's eBPF maps when sessions change

### 2. BNG nftables → eBPF hashmap
- Replace O(n rules) chain traversal with O(1) hashmap lookup
- Python control plane updates BPF map instead of nftables rules
- Same policy logic, fundamentally better data structure
- Would eliminate ksoftirqd saturation across all 4 CPU cores

### 3. SO_ATTACH_FILTER on relay_switch
- cBPF filter to only deliver UDP 67/68 to raw socket
- Eliminates kernel copy of data packets to userspace
- Minor impact (~2% absolute CPU)

## Key Insights
1. **Benchmarking containerized network functions is hard** — shared vCPUs, co-located simulators, and cgroup visibility all confound results
2. **perf top call counts ≠ CPU cost** — Docker DNS chains had 1.6M calls but negligible cost
3. **The bottleneck is architectural** — veth pairs doing full kernel stack traversal at every hop cannot be fixed with a simple eBPF program; requires Cilium-scale effort for full optimization
4. **Real BNGs use dedicated hardware** — ASICs handle packet forwarding without any of this overhead
5. **52MB RSS for BNG control plane** — lightweight despite holding all session state in-memory, because per-session data is just IP/MAC/counters
6. **$6 Hetzner node running 30+ containers** — environment limitation, not software limitation