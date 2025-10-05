# Pricing Model (Transparent Value-Capture Framework)

This document defines how ConsciousDB Sidecar pricing is derived, how it maps to value delivered, and how adjustments are governed over time. It links directly to empirical research and sensitivity analyses so customers and contributors can audit assumptions.

Related: `PRICING_RESEARCH_AND_SIMULATIONS.md` (ROI derivation), raw CSV inputs: `pricing_research_v1.csv`, `pricing_research_v1_summary_advertised.csv`, `pricing_sensitivity_v1.csv` (all in `docs/`).

## 1. Principles
1. Value capture, not pure cost-plus: target 25–45% of realized, customer-visible savings (baseline 35%).
2. Transparent & reproducible: every public tier is backed by a calculable per‑query value model.
3. Elastic scaling: marginal overage price aligns with incremental token + time savings (keeps ROI positive as usage grows).
4. Avoid lock-in: BYO vector DB / embedder optionality means we only charge for retrieval intelligence & explainability layer.
5. Simplicity on surface, rigor underneath: few public plan anchors; detailed model maintained internally but openly documented.

## 2. Economic Value Stack
We estimate monthly gross savings (GS) for a tenant from three channels:

$$GS = S_{tokens} + S_{time} + S_{rerank\_substitution}$$

Where:
- Token savings (S_tokens): fewer follow-up LLM calls & pruned context.
- Time savings (S_time): fewer escalations to humans / analysts.
- Reranker substitution (S_rerank_substitution): avoided spend on external rerank API (if previously used).

Monthly target price (TP) before rounding:
$$TP = r_{capture} * GS \quad \text{with} \quad r_{capture} \in [0.25,0.45], \text{baseline } 0.35$$

We then search a discrete set of candidate per-query prices (currently 0.0005–0.0030 USD) and select the one whose implied monthly spend most closely approaches TP without exceeding by >15%.

## 3. Usage Metrics & Drivers
| Symbol | Description | Source | Notes |
|--------|-------------|--------|-------|
| Q | Monthly queries | Metered | Distinguishes plan tiers |
| f_fu | Baseline follow-up rate | Research baseline (20%) | Portion of queries that cause a second LLM call |
| Δ_accept | Acceptance improvement (5–15%) | Measured per tenant | Drives token/time savings linearly |
| r_esc | Escalation rate (1%) | Customer-calibrated | Fraction of queries escalating to human |
| t_esc | Minutes per escalation (5) | Customer-calibrated | Analyst / support involvement time |
| c_hr | Blended hourly cost ($35) | Customer-calibrated | Can vary widely by vertical |
| p_rerank | External reranker cost ($2/1k) | Public benchmarks | Used only if customer currently pays |
| p_tok_in | Input token $/1k | Model pricing | Commodity LLM baseline |
| p_tok_out | Output token $/1k | Model pricing | Commodity LLM baseline |

## 4. Savings Component Formulas (Baseline Approximation)
Let avg tokens per request = T_in + T_out (e.g., 2,500 + 500 = 3,000 tokens). Tokens saved per avoided follow-up ≈ (T_in + T_out).

1. Token savings:
$$S_{tokens} = Q * f_{fu} * Δ_{accept} * (T_{in}+T_{out})/1000 * (p_{tok\_in\_eff}+p_{tok\_out\_eff})$$
Where effective token prices reflect compression or negotiated discounts if any.

2. Time savings:
$$S_{time} = Q * r_{esc} * Δ_{accept} * (t_{esc}/60) * c_{hr}$$

3. Reranker substitution (if applicable):
$$S_{rerank\_substitution} = Q * p_{rerank}/1000$$
If customer had no reranker previously, this term = 0.

These align with the CSV columns: `token_savings`, `time_savings`, `rerank_savings`.

## 5. Tiering Logic
Public plan anchors (illustrative; map to CSV recommended plan prices):

| Plan | Query Allowance (Q/mo) | Rounded Monthly Price | Effective Included Price per 1K | Overage (Elastic) | Key Features |
|------|------------------------|-----------------------|---------------------------------|-------------------|--------------|
| Free | 10K | $0 | $0.00 | $0.0020 (trial) | Basic diagnostics, community support |
| Developer | 50K | $79 | ~$1.58 | $0.0016 | Dashboard, limited learning, receipts |
| Pro | 500K | $499 | ~$0.998 | $0.0015 | Full explainability, adaptive tuning, SLO metrics |
| Team | 1M | $999 | ~$0.999 | $0.0013 | Multi-tenant config, extended retention |
| Scale | 2M | $1,499 | ~$0.749 | $0.0012 | VPC options, advanced metrics export |
| Enterprise | 5M+ | Custom (ref $0.0008–0.0012/query) | Negotiated | Contract | Premium connectors, private networking, custom SLAs |

Note: Effective price per 1K = (Rounded monthly price / Q) * 1000; differs from overage which is marginal.

## 6. Sensitivity Integration
Acceptance uplift (Δ_accept) is the largest lever. From `pricing_sensitivity_v1.csv`, total savings scale nearly linearly with Δ_accept (5 → 15%). Governance rule: if a tenant's trailing 30‑day measured uplift persists >2 points above the bracket assumed for their tier midpoint, we may propose a per‑query discount/credit to keep value capture within 25–45% band rather than silently over‑capturing.

| Uplift Band | Assumed Δ_accept | Pricing Action |
|-------------|------------------|----------------|
| Low | 0–5% | Monitor; keep standard overage |
| Core | 5–12% | Default pricing (table above) |
| High | >12% | Consider reducing overage or offering reserved capacity commitment discount |

## 7. Premium Connectors & Add-Ons
Premium connectors (e.g., managed Pinecone, Vertex AI, enterprise pgvector) justify an uplift due to:
- Credential management & secure network path (private link / VPC peering)
- Performance SLAs (latency percentiles, availability)
- Specialized optimization (batching, local caching per backend)

Billing Implementation Options:
1. Flat monthly add-on per connector (e.g., $199/connector) after Pro tier.
2. OR percentage uplift on base plan (e.g., +15%) capped by absolute fee.
The model currently favors flat add-ons to keep marginal query economics stable.

## 8. Governance & Adjustment Cadence
| Aspect | Policy |
|--------|--------|
| Review cadence | Quarterly (or when LLM token prices shift >20%) |
| Data inputs | Actual tenant metrics: Δ_accept, Q, escalation stats, reranker usage flag |
| Capture band check | Recompute realized capture%; if outside 25–45%, adjust reserved or overage pricing |
| Change notification | ≥30 days for increases; immediate for decreases or promotional credits |
| Experimentation | A/B overage at two price points for a 10% cohort max |

## 9. Worked Example (Developer Tier)
Given: Q=50K, Δ_accept=10%, f_fu=0.20, r_esc=0.01, t_esc=5, c_hr=$35, tokens=3,000, token blended $/1k=($p_in+$p_out)=assume $0.002 (illustrative), reranker used.

Token savings ≈ 50,000 * 0.20 * 0.10 * 3,000/1000 * 0.002 = $6
Time savings ≈ 50,000 * 0.01 * 0.10 * (5/60) * 35 ≈ $145.83
Rerank substitution ≈ 50,000 * 2 / 1000 = $100
Gross savings ≈ $251.83; target monthly (35%) ≈ $88.14 → rounded public $79 with overage preserving ROI.

## 10. Edge Cases & Adjustments
- No reranker baseline: remove substitution term; Developer tier effective capture then falls → acceptable (land & expand strategy).
- Extremely high uplift vertical (Δ_accept >18%): propose reserved commit discount to maintain fairness while keeping expansion attractive.
- On-prem / air-gapped: add platform fee (infrastructure & support overhead) layered on top of equivalent Scale / Enterprise tier.

## 11. Data References
| File | Purpose | Key Columns |
|------|---------|-------------|
| `pricing_research_v1.csv` | Raw candidate evaluation vs target capture | price_per_query, monthly_spend, target_monthly, token_savings, time_savings, rerank_savings |
| `pricing_research_v1_summary_advertised.csv` | Human-friendly advertised mapping | suggested_plan_price, effective_price_per_1k |
| `pricing_sensitivity_v1.csv` | Uplift sweep | accept_improve, total_savings |

## 12. Future Enhancements
- Per-vertical parameter packs (different escalation cost & reranker prevalence).
- Dynamic reserved capacity discounts (commit X queries for Y% lower overage).
- Automated capture band alerting in OPERATIONS metrics.

## 13. Change Log (Doc Specific)
- 2025-10-05: Rewritten for transparency; added formulas, governance, and explicit linkage to research datasets.

---
For any pricing model PRs: include recalculated capture percentages and note assumptions changed. If token pricing or escalation costs shift materially, update Section 3 & 4 first.
