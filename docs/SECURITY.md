# Security

This document outlines the current security posture, threat model, and roadmap for hardening the ConsciousDB Sidecar.

## Guiding Principles

1. Minimize data residency: operate on embeddings + opaque IDs; avoid storing original source text.
2. Deterministic, inspectable outputs: receipts + audit logs enable after‑the‑fact verification without storing sensitive payloads.
3. Defense in depth through feature flags: adaptive / bandit / audit logging can be independently disabled if risk posture requires.
4. Secure by default: auth enabled when `API_KEYS` set; dimension mismatch fails fast unless explicitly overridden.

## Assets & Data Classes

| Asset | Description | Sensitivity | Notes |
|-------|-------------|-------------|-------|
| Query Text | End‑user natural language query | Medium | Transient in process memory & logs only if explicitly logged (we do not). |
| Embeddings (query + recalled vectors) | Float vectors | Medium | No direct semantic reversal assumed, but treat as derived sensitive. |
| IDs of documents | Opaque identifiers | Low | May become sensitive if IDs leak structure or internal keys. |
| Audit Log (`audit.log`) | Per‑query structured diagnostics | Medium | Omits raw embeddings; can be HMAC signed. |
| Feedback Log (`feedback.log`) | User interaction events | Medium | Contains query_id linkage. |
| Adaptive State (`adaptive_state.json`) | Rolling stats, bandit arms | Low/Medium | No user content; tuneable parameters only. |
| API Keys | Shared secret header values | High | Must never be logged; constant‑time compare implemented. |
| HMAC Key (`AUDIT_HMAC_KEY`) | Integrity secret for audit lines | High | Optional; strengthens tamper detection. |

## Trust Boundaries

1. Client / Sidecar boundary: authenticated via API key (header `x-api-key` by default).
2. Sidecar / Vector DB boundary: network egress to managed vector store (pgvector / Pinecone / etc.).
3. Sidecar / Persistent Logs boundary: local filesystem (container ephemeral or mounted volume).
4. Sidecar / Secret Source boundary: environment variables (recommended: inject via orchestration secret manager).

## Threat Model

| ID | Threat | Vector | Impact | Likelihood | Current Mitigation | Gaps / Planned |
|----|--------|--------|--------|------------|--------------------|----------------|
| T01 | API key theft | Env var leakage / repo commit | Full query access | Medium | Keys not committed; doc guidance to use secret manager | Key rotation endpoint (future); per‑key scopes |
| T02 | Brute force auth | Credential stuffing | Unauthorized usage | Low | Random opaque keys; constant‑time compare; no verbose errors | Rate limiting / lockout pending |
| T03 | Log exfiltration | Read container FS | Exposure of diagnostics | Medium | Minimal fields; no raw content; optional HMAC for integrity | Encrypt at rest (optional volume) |
| T04 | Tampering with audit log | Post‑write modification | Loss of forensic integrity | Medium | Optional HMAC signature per line | Periodic remote shipping + verification service |
| T05 | Prompt / embedding leak via monitoring | Over‑broad logging | Data disclosure | Low | Structured logs exclude query text (except easy gate optional events) | Add explicit redaction layer / allowlist fields |
| T06 | DoS via expensive queries | Large M / high iteration | Resource exhaustion | Medium | Iteration caps (`ITERS_CAP`), residual tolerance, early gates | Global rate limits; per‑tenant quotas |
| T07 | Adaptive poisoning | Malicious feedback events | Ranking degradation | Low | Feedback recorded locally; bounded buffer; correlation‑based alpha only | Anomaly detection; signature on feedback batch |
| T08 | State deserialization attack | Malicious adaptive_state file | Code execution / corruption | Low | JSON only; pydantic validation | Add checksum / HMAC for state file |
| T09 | Vector DB credential leak | Misconfigured env / logs | External DB exposure | Medium | Credentials only via env; never logged | Dynamic secret rotation integration |
| T10 | Sidecar SSRF (future embeddings calling remote) | Crafted model requests | Data exfiltration | Low | Current embedders local / vendor SDKs only | Egress allow‑list for future HTTP embedders |

## Implemented Controls

| Category | Control | Status |
|----------|---------|--------|
| AuthN | Static API key header | Implemented |
| AuthZ | Per‑tenant segmentation (key = tenant) | Minimal (no scopes) |
| Rate Limiting | Per‑key / global limits | Planned |
| Input Validation | Embedding dimension check | Implemented |
| Resource Safety | CG iteration + residual caps | Implemented |
| Privacy Minimization | No source docs stored; embeddings transient | Implemented |
| Logging Hygiene | JSON structured logs, minimal PII | Implemented |
| Audit Integrity | Per‑line HMAC (optional) | Implemented |
| Secret Handling | Env var loading via `infra.secrets.get_secret` | Implemented (basic) |
| Secret Rotation | Hot reload | Planned |
| Adaptive Safety | Bounded event buffer; correlation thresholding | Implemented |
| Supply Chain | Pinned deps via `pyproject.toml` (versions may float pre‑lock) | Partial |
| Transport Security | Rely on upstream TLS termination (ingress) | External dependency |
| Data Isolation | No multi‑tenant shared persistent state (unless enabled) | Implemented |

## Configuration Hardening Flags

| Env Var | Security Effect |
|---------|-----------------|
| `API_KEYS` | Enables API authentication (empty disables). |
| `AUDIT_HMAC_KEY` | Adds integrity signature to each audit line. |
| `FAIL_ON_DIM_MISMATCH` | Prevent silent vector shape drift. |
| `ENABLE_ADAPTIVE` / `ENABLE_BANDIT` | Disable if deterministic repeatability required. |
| `ENABLE_AUDIT_LOG` | Turn off if strict data minimization required. |

## Audit Log Integrity Verification (Example)

1. For each line, extract the `signature` field.
2. Recompute `hex = HMAC_SHA256(AUDIT_HMAC_KEY, canonical_json(line_without_signature))`.
3. Compare constant‑time; flag mismatches.
4. (Planned) Ship to remote verifier service for append‑only attestation.

## Operational Recommendations

| Scenario | Recommended Setting |
|----------|--------------------|
| High sensitivity (PII adjacency) | Disable `ENABLE_AUDIT_LOG`; ensure TLS at ingress; restrict egress CIDRs. |
| Benchmark / Load test | Disable adaptive/bandit for determinism. |
| Forensic mode | Enable audit + HMAC + short rotation cadence shipping to object store. |

## Roadmap (Security)

Short term (next 2 minor releases):
- Rate limiting middleware with token bucket per API key.
- Config reference documentation (central matrix).
- Checksum / HMAC for adaptive state file.

Medium term:
- Key rotation endpoint + inactive key revocation.
- Structured remote audit exporter (OTel / syslog).
- Optional envelope encryption for local logs.

Long term:
- Per‑item differential privacy noise (optional) on coherence metrics.
- Multi‑party computation research track for cross‑tenant similarity suppression.

## Residual Risks

Risks T02 (rate limiting), T07 (adaptive poisoning), and T04 (audit tamper without HMAC) remain partially mitigated until planned controls land. Deploy behind an API gateway (or service mesh) that enforces mTLS + global quotas in the interim.

## Change Log (Doc)

| Date | Change |
|------|--------|
| 2025-10-05 | Initial comprehensive expansion (threat model, controls). |
