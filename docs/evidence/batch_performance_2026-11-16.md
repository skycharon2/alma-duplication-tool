# Batch profiler smoke baseline — 2026-11-16

Base: `e54100b`, plus the profiler increment accompanying this record.
Scientific rules are unchanged. These measurements use a tiny Queue fixture and
a replay cone that does not match all five targets; they are **not** evidence of
production speed or successful live Archive acquisition.

| Sources | Workers | Wall seconds | Peak RSS MiB | Retained bytes |
|---|---:|---:|---:|---:|
| archive | 1 | 0.0245 | 121.2 | 176125 |
| archive | 2 | 0.0237 | 120.9 | 176125 |
| both | 1 | 0.0606 | 122.3 | 777152 |
| both | 2 | 0.0618 | 123.4 | 777152 |
| queue | 1 | 0.0589 | 121.3 | 757087 |
| queue | 2 | 0.0553 | 123.0 | 757087 |

[Machine-readable stages, source statuses and input hashes](batch_performance_2026-11-16.json).
Each measurement used a fresh process. No speedup is inferred from single trials.
Full-snapshot and live measurements remain outstanding; this record establishes
the reproducible measurement path and failure-status visibility only.
