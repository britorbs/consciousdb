# Algorithm & math

We solve
\[
M Q = \lambda_G X + \lambda_Q b y^\top, \qquad
M = \lambda_G I + \lambda_C L_{\mathrm{sym}} + \lambda_Q B,
\]
where \(L_{\mathrm{sym}} = I - D^{-1/2} A D^{-1/2}\), \(B = \mathrm{diag}(b)\), \(b \ge 0\), \(\sum b_i = 1\).

- **SPD**: \(L_{\mathrm{sym}} \succeq 0\), \(B \succeq 0\). With \(\lambda_G>0\), \(M \succ 0\) ⇒ CG is applicable and stable.
- **Gates**:
  - **Easy-query**: if \( \cos_{(1)} - \cos_{(10)} > \delta \), skip solve.
  - **Low-impact**: if total \( \sum_i \big(\text{coh}_i^{base} - \text{coh}_i^{star}\big) < \epsilon \), skip ΔH re-rank.
- **Ranking** (from findings):
  \[
  \text{score}_i = \alpha \cdot z\big(\text{coherence\_drop}_i\big) + (1-\alpha) \cdot \cos(q_i^\star, y),
  \]
  where \(q_i^\star\) is the solved embedding row; use **coherence-only** for ΔH and do **not** include anchor/ground in the ranker.

- **1-hop expansion**: for tiny gaps, induce context on \(S \cup \mathcal{N}(S)\) (capped to ~1.5×M), **rank only S**.
