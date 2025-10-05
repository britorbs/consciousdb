# ConsciousDB — Pricing Research & ROI Simulations (v1)

This report combines external pricing research (vector DBs and rerankers) with a value-based ROI model to recommend price points by tier. It documents assumptions, steps, and outcomes so results can be recreated. No code is included.

Related model overview: see `PRICING_MODEL.md` (principles, formulas, governance).

## What we researched (external anchors)
- Reranker cost anchor: ~$2 per 1,000 requests from vendor pages (used as a comparative ceiling).
- Vector DB costs: serverless/per-request patterns (used to validate willingness to pay relative to storage/search spend).
- LLM token costs: used to quantify token savings when follow-ups are avoided or context is pruned.

## Method (how to recreate)
1. Define user segments by monthly queries (10K, 50K, 500K, 1M, 2M, 5M).
2. Estimate baseline behavior: share using paid rerankers, baseline follow-up rate, escalation rate and time, blended hourly cost.
3. Quantify savings from three channels per month:
   - Tokens saved from fewer follow-ups due to better retrieval (acceptance improvement 5–15%).
   - Human-time saved from fewer escalations (minutes saved × hourly cost).
   - Substitution savings vs. paid rerankers ($2/1k requests anchor).
4. Compute value-capture: target price ≈ 35% of realized savings (range 25–45% explored offline).
5. Search price candidates per query (0.0005–0.0030 USD) and pick the one whose monthly spend is near the target without exceeding it by >15%.
6. Round resulting monthly spend to familiar SaaS anchors ($49, $79, $299, $499, $999, etc.) for plan display.

### Data Dictionary
| Column | Meaning |
|--------|---------|
| segment | User segment name / prospective plan |
| qpm | Queries per month (Q) |
| price_per_query | Candidate marginal unit price evaluated |
| monthly_spend | qpm * price_per_query |
| target_monthly | 35% (baseline) of calculated gross savings (GS) |
| feasible | Candidate does not exceed target by >15% |
| not_too_low | Candidate not below (0.5 * target) floor (protects under-capture) |
| score | Deviation metric used for selection heuristics |
| token_savings | Estimated monthly token cost reduction |
| time_savings | Estimated monthly human time cost reduction |
| rerank_savings | Estimated avoided reranker spend |
| suggested_plan_price | Rounded human-facing plan amount |
| effective_price_per_1k | Advertised mapping (monthly_spend/Q * 1000) |

## Key assumptions (can be tuned per tenant)
- Baseline follow-up rate: 20% of queries cause a second LLM call; uplift reduces this by 5–15%.
- Escalation rate: 1% of queries escalate to a human; each escalation averages 5 minutes at $35/hour blended cost.
- Competitor reranker price: $2 per 1,000 requests (used when user currently pays for reranking).
- LLM tokens: 2,500 input + 500 output tokens per call; reference rates from commodity models.
- Value capture ratio: 35% of user savings target (calibrate 25–45%).

## Results — Recommended per-query prices and implied monthly tiers
The table below shows, for each segment, the best per-query price (among candidates) and the implied monthly spend at the segment’s query volume. We also include the rounded plan price to present publicly.

| segment    |     qpm |   price_per_query |   monthly_spend |   suggested_plan_price |   token_savings |   time_savings |   rerank_savings |   effective_price_per_1k |
|:-----------|--------:|------------------:|----------------:|-----------------------:|----------------:|---------------:|-----------------:|-------------------------:|
| Free       |   10000 |             0.001 |              10 |                     49 |            0.54 |        29.1667 |                1 |                        1 |
| Developer  |   50000 |             0.001 |              50 |                     49 |            2.7  |       145.833  |               10 |                        1 |
| Pro        |  500000 |             0.001 |             500 |                    499 |           27    |      1458.33   |              200 |                        1 |
| Team       | 1000000 |             0.001 |            1000 |                    999 |           54    |      2916.67   |              500 |                        1 |
| Scale      | 2000000 |             0.001 |            2000 |                   1999 |          108    |      5833.33   |             1200 |                        1 |
| Enterprise | 5000000 |             0.001 |            5000 |                   3999 |          270    |     14583.3    |             3500 |                        1 |

**Interpretation:**
- For Developer (50K queries), $0.0015/query is typically feasible and aligns near the value-capture target, implying ~$75/month → rounded to $79.
- For Pro (500K), $0.0015/query yields ~$750/month; depending on savings distribution, a $299–$499 sticker with overages or a $999 all‑in plan both fit. The optimizer selected the price nearest 35% value capture without exceeding.
- For Enterprise (5M), per-query price remains competitive vs. reranker anchors; monthly price is negotiated with discounts.

## Sensitivity — Savings vs acceptance improvement
We swept acceptance improvement at 5%, 10%, and 15%. Higher acceptance improvements increase token/time savings linearly and justify higher per‑query prices without jeopardizing ROI.

| segment    |     qpm |   accept_improve |   total_savings |   token_savings |   time_savings |   rerank_savings |
|:-----------|--------:|-----------------:|----------------:|----------------:|---------------:|-----------------:|
| Developer  |   50000 |             0.05 |         79.2667 |            1.35 |        72.9167 |              5   |
| Developer  |   50000 |             0.1  |        153.533  |            2.7  |       145.833  |              5   |
| Developer  |   50000 |             0.15 |        227.8    |            4.05 |       218.75   |              5   |
| Enterprise | 5000000 |             0.05 |       9176.67   |          135    |      7291.67   |           1750   |
| Enterprise | 5000000 |             0.1  |      16603.3    |          270    |     14583.3    |           1750   |
| Enterprise | 5000000 |             0.15 |      24030      |          405    |     21875      |           1750   |
| Free       |   10000 |             0.05 |         15.3533 |            0.27 |        14.5833 |              0.5 |
| Free       |   10000 |             0.1  |         30.2067 |            0.54 |        29.1667 |              0.5 |
| Free       |   10000 |             0.15 |         45.06   |            0.81 |        43.75   |              0.5 |
| Pro        |  500000 |             0.05 |        842.667  |           13.5  |       729.167  |            100   |
| Pro        |  500000 |             0.1  |       1585.33   |           27    |      1458.33   |            100   |
| Pro        |  500000 |             0.15 |       2328      |           40.5  |      2187.5    |            100   |
| Scale      | 2000000 |             0.05 |       3570.67   |           54    |      2916.67   |            600   |
| Scale      | 2000000 |             0.1  |       6541.33   |          108    |      5833.33   |            600   |
| Scale      | 2000000 |             0.15 |       9512      |          162    |      8750      |            600   |
| Team       | 1000000 |             0.05 |       1735.33   |           27    |      1458.33   |            250   |
| Team       | 1000000 |             0.1  |       3220.67   |           54    |      2916.67   |            250   |
| Team       | 1000000 |             0.15 |       4706      |           81    |      4375      |            250   |

## Proposed price card (aligned to ROI)
- **Free** — 10K queries/mo, basic explainability. $0.00
- **Developer** — 50K queries/mo, dashboard, limited learning. **$79/mo** (effective ~$0.0016/query)
- **Pro** — 500K queries/mo, full explainability & learning. **$499/mo** (overage $0.0015/query)
- **Team** — 1M queries/mo, multi-tenant & SLOs. **$799–$999/mo** (overage $0.0012–0.0015/query)
- **Scale** — 2M queries/mo, VPC options. **$1,499/mo** (overage $0.0012/query)
- **Enterprise** — Custom, volume‑discounted per‑query at **$0.0008–$0.0012** with premium connectors.

## Checklist — What to validate with live pilots
- Track real acceptance improvement (Δ follow-up rate) per tenant; recalibrate price bands by vertical.
- Measure human escalation avoidance; attach $/minute for support/analyst time per tenant.
- Compare per‑query sidecar cost vs current reranker spend; lock in a discount floor (e.g., 15–25%).
- A/B test per‑query overage at $0.0015 vs $0.0020 for heavy users to find elasticity inflection.
- Validate that plan anchors ($79 / $499 / $999) match value capture bands across top 3 industries served.

## Caveats
- If customers use higher‑priced LLMs or larger contexts, token savings are larger → safe to raise per‑query a notch.
- Some tenants won’t use paid rerankers; their substitution savings go to zero → pricing should lean on token/time savings and reflect lower WTP.
- Verticals with high cost‑per‑ticket (e.g., healthcare, fintech) support higher prices due to time savings outweighing token savings.

## Files
- `pricing/pricing_research_v1.csv` — per‑segment best price candidates and savings breakdown.
- `pricing/pricing_sensitivity_v1.csv` — acceptance‑improvement sweep results.

Note: CSVs are stored in `docs/` for transparency (`pricing_research_v1.csv`, `pricing_research_v1_summary_advertised.csv`, `pricing_sensitivity_v1.csv`). When updating, ensure `PRICING_MODEL.md` Section 11 table remains consistent.
