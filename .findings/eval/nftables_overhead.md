# Proof of nftables causing network slowdown in hosted platform

This test was ran on Hetzner shared 4vCPU and 8 GB Ram 

### Before iperf3 test with simulated subscribers in the background
```
perf top | head -20

   PerfTop:       0 irqs/sec  kernel: 0.0%  exact:  0.0% lost: 0/0 drop: 0/0 [4000Hz cycles:P],  (all, 4 CPUs)
-------------------------------------------------------------------------------

   PerfTop:    4857 irqs/sec  kernel:43.8%  exact:  0.0% lost: 0/0 drop: 0/0 [4000Hz cycles:P],  (all, 4 CPUs)
-------------------------------------------------------------------------------

     4.38%  perf                     [.] rb_next
     3.85%  perf                     [.] kallsyms__parse
     3.39%  [kernel]                 [k] kallsyms_expand_symbol.constprop.0
     3.32%  perf                     [.] io__get_char
     3.27%  perf                     [.] io__get_hex
     1.93%  [kernel]                 [k] number
     1.83%  [kernel]                 [k] format_decode
     1.51%  [kernel]                 [k] vsnprintf
     1.49%  [kernel]                 [k] string
     1.46%  perf                     [.] map__process_kallsym_symbol
     1.27%  [kernel]                 [k] zap_pte_range
     1.11%  [kernel]                 [k] next_uptodate_folio
```

### During iperf3 test with simulated subscribers in the background
```
perf top | head -20

   PerfTop:       0 irqs/sec  kernel: 0.0%  exact:  0.0% lost: 0/0 drop: 0/0 [4000Hz cycles:P],  (all, 4 CPUs)
-------------------------------------------------------------------------------

   PerfTop:   11169 irqs/sec  kernel:74.2%  exact:  0.0% lost: 0/0 drop: 0/0 [4000Hz cycles:P],  (all, 4 CPUs)
-------------------------------------------------------------------------------

    27.16%  [kernel]       [k] nft_do_chain
    11.39%  [kernel]       [k] nft_meta_get_eval
     3.29%  [kernel]       [k] init_nls_iso8859_1
     1.31%  perf           [.] kallsyms__parse
     1.19%  perf           [.] rb_next
     1.06%  [kernel]       [k] kallsyms_expand_symbol.constprop.0
     1.06%  [kernel]       [k] rep_movs_alternative
     0.93%  perf           [.] io__get_hex
     0.87%  perf           [.] io__get_char
     0.65%  [kernel]       [k] number
     0.61%  [kernel]       [k] retbleed_return_thunk
     0.56%  [kernel]       [k] memset_orig
```

The nftables looks like a bottleneck. Although, I am not too sure about it. Requires more research!