# Resource & Reliability Specification

## 1. Objective

The engine must be resource-bounded, portable, observable, and resilient under constrained hardware. Reliability means predictable behavior under failure, not the impossible promise of zero failures.

## 2. Supported execution profiles

### CPU-minimal
For CPU-only or low-memory machines.
- small bounded batches;
- limited worker count;
- reranker optional/off by policy;
- remote generation preferred when local generation exceeds budget.

### Balanced
Normal workstation/server execution.

### Accelerated
GPU available with sufficient memory.
- GPU used only where measured beneficial;
- CPU indexes remain where appropriate;
- model residency explicitly managed.

### Remote-LLM
Retrieval/evidence locally or on service infrastructure; generation via remote API.

Profiles are policy presets, not hard-coded device assumptions.

## 3. Resource discovery

At startup or profile resolution, inspect:

```text
OS
CPU count
CPU memory
GPU availability
GPU memory
GPU compute capability when available
Python/runtime version
model/runtime compatibility
storage availability
```

Discovery must not fail the application merely because optional hardware probes are unavailable.

## 4. Resource budget

Every major operation has bounded:

- workers;
- queue size;
- batch size;
- sequence length;
- candidate count;
- retry count;
- timeout;
- memory target.

No unbounded task spawning, retry loops, or in-memory accumulation.

## 5. Model residency

Under constrained VRAM:

```text
retriever encoder
      OR
reranker
      OR
generator
```

may be resident when simultaneous residency would exceed the verified budget.

Prefer offload/unload and staged execution over predictable OOM.

## 6. Retrieval efficiency

- BM25 is CPU-first.
- FAISS is CPU-first unless a measured deployment requires otherwise.
- Dense query encoding should use inference mode.
- Candidate counts should be bounded.
- Avoid re-encoding unchanged corpus text at query time.
- Indexes must be persisted/versioned rather than rebuilt per request.

## 7. Reranking efficiency

Reranking must use bounded batch inference.

Benchmark:

```text
batch size
candidate count
sequence length
latency p50/p95
CPU
RAM
VRAM
throughput
```

The optimization objective is not minimum latency at any cost. It is the best measured quality/resource trade-off for the selected profile.

## 8. Adaptive execution

When memory pressure is detected:

```text
normal batch
  ↓
pressure
  ↓
reduce batch
  ↓
retry once within bounded policy
  ↓
success OR degrade
```

Adaptive behavior must be deterministic and logged.

## 9. Fault taxonomy

Minimum classes:

```text
INVALID_INPUT
DATA_CORRUPTION
ARTIFACT_MISSING
ARTIFACT_INCOMPATIBLE
MODEL_LOAD_FAILURE
OUT_OF_MEMORY
TIMEOUT
BACKEND_FAILURE
RATE_LIMIT
DEPENDENCY_FAILURE
RETRIEVAL_MISS
EVIDENCE_INSUFFICIENT
CITATION_MISMATCH
JURISDICTION_CONFLICT
TEMPORAL_CONFLICT
UNKNOWN
```

## 10. Recovery policy

Every recoverable fault has an explicit bounded policy.

Examples:

- OOM → reduce batch / offload / fallback backend;
- model-load failure → fallback model/backend if configured;
- remote 429 → bounded backoff and alternate backend if available;
- corrupted artifact → quarantine and fail closed;
- retrieval miss → return insufficient evidence rather than hallucinating;
- citation mismatch → reject/repair generation through controlled path;
- temporal conflict → surface warning and select verified applicable version when possible.

A failure must never trigger unlimited retries.

## 11. Failure learning

Runtime failures generate a normalized `FailureEvent` where policy permits.

```text
failure_id
request_id
operation
stage
error_class
error_signature
software_version
model_version
knowledge_release
dataset_version
execution_profile
hardware_summary
resource_signals
recovery_action
recovery_result
sanitized_context
```

Failure events may be promoted into regression/evaluation cases after sanitization and review.

They must not directly modify production code, thresholds, prompts, or model weights.

## 12. Observability

Each important operation should expose:

- request/query identifier;
- stage timings;
- selected execution profile;
- model/backend;
- knowledge release;
- retriever/reranker version;
- resource signals;
- warnings;
- recovery action;
- outcome.

Instrumentation should remain lightweight. High-cardinality or sensitive payload logging is prohibited by default.

## 13. SLO-style targets

Before declaring production SLOs, collect workload data. Early targets should be expressed as measurement gates rather than arbitrary promises.

Record:

```text
p50 latency
p95 latency
error rate
recovery rate
availability
resource ceiling violations
```

## 14. Portability

The same domain code should operate on:

- Windows 10/11;
- WSL2;
- Linux;
- CPU-only;
- constrained GPU;
- modern GPU;
- remote inference.

Platform-specific behavior must live behind isolated runtime adapters.

## 15. Startup and lifecycle rules

- Heavy models and indexes load at controlled lifecycle boundaries.
- No request-time model download.
- No rebuilding the corpus index for a normal query.
- Health and readiness are distinct.
- Shutdown should release model resources cleanly.

## 16. Reliability gates

A stage is not complete if:

- recovery behavior is unbounded;
- failures are silently swallowed;
- resource usage is unmeasured for a resource-sensitive change;
- restart leaves corrupted or ambiguous state;
- a fallback changes legal semantics silently.
