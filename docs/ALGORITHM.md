# Algorithm & Math (Normalized Only)

We solve the SPD linear system
\[
M Q = \lambda_G X + \lambda_Q b y^\top, \qquad M = \lambda_G I + \lambda_C L_{\mathrm{sym}} + \lambda_Q B,
\]
with normalized Laplacian \(L_{\mathrm{sym}} = I - D^{-1/2} A D^{-1/2}\) and anchor diagonal \(B=\operatorname{diag}(b), b\ge 0, \sum b_i = 1\).

## Properties
- **SPD**: \(L_{\mathrm{sym}} \succeq 0\), \(B \succeq 0\); with \(\lambda_G>0\) ⇒ \(M \succ 0\) so block Conjugate Gradient is stable.
- **Easy-query gate**: if \(\cos_{(1)} - \cos_{(10)} > \delta\) skip solve (return vector-only ranking).
- **Low-impact gate**: if provisional ΔH < ε skip coherence blending.
- **1-hop expansion**: when similarity gap small, optionally expand context to neighbors then restrict ranking to original S.

## Ranking Function
\[
	ext{score}_i = \alpha\, z(\text{coherence\_drop}_i) + (1-\alpha)\, \cos(q_i^\star, y),
\]
where \(q_i^\star\) is the solved row. Anchor and ground terms regularize the solve but are not directly added to the rank score.

## Energy Gap Identity
Define baseline solution (no anchor) \(Q_{base}\) and anchored solution \(Q_\star\). The energy improvement is
\[
\Delta H = H(Q_{base}) - H(Q_\star) = \lambda_G (\|Q_{base}-X\|_F^2 - \|Q_\star - X\|_F^2) + \lambda_C (Q_{base}^T L Q_{base} - Q_\star^T L Q_\star) + \lambda_Q ((Q_{base}-y)^T B (Q_{base}-y) - (Q_\star - y)^T B (Q_\star - y)).
\]
Per-node coherence attribution uses the quadratic form:
\[
Q^T L Q = \sum_i q_i^T (L q)_i.
\]
We guarantee conservation: \(\sum_i \text{coherence\_drop}_i = \text{deltaH\_total}\) (± FP tolerance) and expose `deltaH_trace` as an independent quadratic check.

## Scope Divergence
`deltaH_scope_diff = |\Delta H_{full} - \Delta H_{topk}| / (|\Delta H_{full}| + \varepsilon)` quantifies energy remaining outside the returned top-k; values ~0.3–0.4 are typical when k ≪ M.
