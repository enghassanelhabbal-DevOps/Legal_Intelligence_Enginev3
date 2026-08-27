# System Component Specification

## 1. Purpose

Define stable component responsibilities and interfaces so implementation can evolve without duplicating business logic or coupling the legal domain to a specific model/provider.

## 2. Component map

```text
UI / API
   ↓
Query Service
   ↓
Query Understanding
   ↓
Retrieval Planner
   ↓
Dense + Lexical Retrieval
   ↓
Filtering / Candidate Union
   ↓
Reranker
   ↓
Evidence Builder
   ↓
Support / Conflict Validator
   ↓
Generation Adapter
   ↓
Answer Validator
   ↓
Response
```

Cross-cutting:

```text
Resource Manager
Failure Manager
Telemetry
Evaluation
Knowledge Release Manager
```

## 3. Core interfaces

### QueryRequest

Should eventually represent:

```text
query
language?
jurisdiction?
country?
as_of_date?
legal_domain?
question_type?
requested_authority_types?
mode?
client_context?
```

Explicit user constraints take precedence over inferred values.

### QueryUnderstanding

```text
language
jurisdiction
legal_domain
reference_date
intent
question_type
single_or_multi_hop
required_evidence_types
ambiguity_flags
risk_flags
```

All inferred fields should carry confidence or an explicit unknown state where meaningful.

### RetrievalPlan

```text
retrievers
candidate_limits
filters
jurisdiction_scope
temporal_scope
authority_scope
reranker
final_k
```

The plan is an execution recommendation, not a legal conclusion.

### RetrievalHit

Must preserve stable document identity and ranking metadata.

### EvidenceItem

Must preserve the source span and provenance used for a claim.

### EvidenceSet

Represents the evidence selected for one answer and records completeness/sufficiency state.

### Answer

Should eventually contain:

```text
answer
claims
citations
evidence
warnings
abstention
confidence/uncertainty
timing
resource_info
release/model metadata
```

## 4. Knowledge components

### Ingestion
Input: raw source.
Output: validated canonical legal records.

### Normalization
Produces derived retrieval text only. Original source must remain available.

### Version manager
Creates explicit version/effective-period relationships.

### Release manager
Builds immutable knowledge releases and supports rollback.

## 5. Retrieval components

### DenseRetriever
Semantic candidate generation.

### LexicalRetriever
Exact/legal-term matching.

### CandidateFusion
Combines candidate pools without losing strong evidence from either head.

### MetadataFilter
Applies explicit jurisdiction/time/authority constraints.

### Reranker
Scores candidate relevance using a replaceable model.

No component may mutate canonical legal meaning merely to improve ranking.

## 6. Evidence components

### EvidenceBuilder
Transforms ranked candidates into a bounded evidence set.

### SupportValidator
Determines whether evidence supports a claim.

### CitationValidator
Ensures citations resolve to supplied evidence and canonical source metadata.

### ConflictDetector
Identifies possible version/jurisdiction/authority/text conflicts for review.

## 7. Generation components

### GenerationAdapter
Stable abstraction for local or remote LLMs.

Canonical production/provider implementations live under `src/legal_ai/generation/backends/` and must conform to the same adapter contract.

Supported or planned backends are:

- local Transformers backends;
- **Gemini** through a canonical `GeminiBackend`;
- OpenAI-compatible APIs;
- Ollama;
- vLLM;
- future providers that satisfy the same contract.

### Gemini provider requirements

Gemini is treated as a named remote provider because it is part of the current production path. Its provider-specific behavior must be encapsulated in `generation/backends/` rather than root/UI code.

The canonical Gemini implementation must preserve, through tests and measured parity where applicable, the production behaviors currently depended upon by the system, including:

- bounded retries;
- retry/backoff handling for transient provider failures;
- model-variant fallback ordering;
- safe timeout handling;
- provider response normalization;
- structured error mapping;
- no credential leakage in logs or responses.

Provider-specific tuning (for example model IDs or provider request parameters) belongs in configuration/adapter code, not in retrieval, evidence, API, or UI modules.

### Remote-provider data boundary

A remote LLM provider is a trust boundary. The generation layer must make the selected provider explicit to telemetry and policy enforcement.

Before sending a request to a remote provider, the system must apply the configured data-boundary policy and must not silently transmit data classified as disallowed for that provider.

### AnswerValidator

Rejects malformed, unsupported, or untraceable outputs.

## 8. Runtime components

### ResourceManager
Selects execution profile and budgets CPU/RAM/VRAM/parallelism.

### FaultManager
Maps exceptions/events to bounded recovery policies.

### TelemetryManager
Captures low-cost structured measurements.

## 9. Evaluation components

Evaluation must be callable independently of the production UI/API.

Inputs:
- versioned dataset;
- knowledge release;
- software commit/config;
- model versions;
- execution profile.

Outputs:
- metrics;
- per-case results;
- resource report;
- regression decision.

## 10. Dependency rules

Forbidden:

```text
UI → retrieval internals
UI → LLM internals
API → ranking algorithms
Generation → retrieval implementation
Retrieval → provider-specific LLM logic
Runtime backend → duplicated resource policy
Root deployment entrypoint → vendored retrieval/generation business logic
```

Allowed:

```text
API/UI → services
services → stable interfaces
retrieval → core contracts
knowledge → core contracts
engineering/evaluation → stable interfaces and artifacts
generation → provider adapters through the canonical interface
```

The Streamlit deployment constraint does not justify duplicating retrieval or generation behavior. Embedded mode must still invoke the canonical `QueryService` and backend adapters in-process.

## 11. Caching

Cache only immutable or safely versioned objects.

Cache keys should include relevant identity such as:

```text
knowledge_release
query normalization version
retriever version
reranker version
model/backend version
execution policy
request scope/tenant where applicable
```

Never allow stale cache entries to silently substitute a different legal version or provider policy.

## 12. Concurrency

Concurrency is bounded at service/runtime level. Components must not independently create unbounded executors.

## 13. Error contract

Errors should be typed by category and carry safe contextual metadata. API layers translate internal errors into stable external responses.

Provider errors must preserve enough classification to distinguish transient failures, rate limits, timeouts, authentication/configuration errors, malformed responses, and permanent unsupported-model errors without exposing secrets.

## 14. Versioning

When an interface changes incompatibly:

- update the contract;
- add migration notes;
- update tests;
- record a decision;
- avoid leaving two active business-logic implementations.

## 15. Testability

Each component should support deterministic tests with injected dependencies. Model-heavy behavior must have lightweight mocks/fakes for unit tests and real benchmark paths for integration validation.

## 16. Provider migration rule

When a provider currently implemented outside the canonical generation layer is migrated:

1. inventory current production behavior;
2. define canonical adapter contract;
3. implement provider backend;
4. add behavior/parity tests;
5. route the canonical service through the adapter;
6. validate metrics/resource/failure behavior;
7. remove the old implementation;
8. search the repository to confirm no active duplicate remains.

No provider migration is complete while two independently active implementations can serve production answers.
