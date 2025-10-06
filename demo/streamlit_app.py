from __future__ import annotations

import json
import os
from typing import Any

import requests
import streamlit as st

API_URL = os.getenv("CONSCIOUSDB_API", "http://localhost:8080")
DEFAULT_K = int(os.getenv("DEMO_K", "6"))
DEFAULT_M = int(os.getenv("DEMO_M", "400"))

st.set_page_config(page_title="ConsciousDB Demo", layout="wide")
st.title("ConsciousDB – Coherence Receipt Sandbox")

with st.sidebar:
    st.header("Query Parameters")
    k_val = st.number_input("Top K (reranked)", min_value=1, max_value=50, value=DEFAULT_K, step=1)
    m_val = st.number_input("Recall M (candidate pool)", min_value=k_val, max_value=1000, value=DEFAULT_M, step=50)
    alpha = st.slider("Alpha (coherence weight)", 0.0, 0.5, 0.1, 0.01)
    sim_gap = st.slider("Similarity Gap Margin", 0.0, 0.5, 0.15, 0.01)
    residual_tol = st.select_slider("Residual Tolerance", options=[0.0005, 0.001, 0.002], value=0.001)
    iters_cap = st.select_slider("CG Iter Cap", options=[10, 15, 20, 25], value=20)
    receipt_detail = st.radio("Receipt Detail", options=["summary", "full"], index=1)
    show_raw = st.checkbox("Show Raw Response JSON", value=False)
    use_mmr = st.checkbox("Force MMR", value=False)

query = st.text_input("Enter a semantic query", value="vector governance controls")
col_run, col_reset = st.columns([1,1])

if col_reset.button("Reset Query"):
    st.experimental_rerun()

run_clicked = col_run.button("Run Search", type="primary")

if run_clicked and query.strip():
    payload: dict[str, Any] = {
        "query": query.strip(),
        "k": int(k_val),
        "m": int(m_val),
        "overrides": {
            "alpha_deltaH": alpha,
            "similarity_gap_margin": sim_gap,
            "coh_drop_min": 0.01,
            "expand_when_gap_below": 0.08,
            "iters_cap": int(iters_cap),
            "residual_tol": float(residual_tol),
            "use_mmr": bool(use_mmr),
        },
        "receipt_detail": 1 if receipt_detail == "full" else 0,
    }
    with st.spinner("Querying sidecar..."):
        try:
            r = requests.post(f"{API_URL}/query", json=payload, timeout=60)
            if r.status_code != 200:
                st.error(f"API error {r.status_code}: {r.text}")
            else:
                data = r.json()
                diag = data.get("diagnostics", {})
                tabs = st.tabs(["Results", "Receipt", "Graph", "Perf"])  # Graph placeholder
                with tabs[0]:
                    items = data.get("items", [])
                    if not items:
                        st.warning("No items returned.")
                    for i, it in enumerate(items, start=1):
                        with st.expander(f"Rank {i}: {it['id']}"):
                            score_line = (
                                f"**Score:** {it['score']:.4f}  |  **Align:** {it['align']:.4f}  |  "
                                f"**Baseline:** {it['baseline_align']:.4f}"
                            )
                            st.markdown(score_line)
                            et = it.get("energy_terms", {})
                            st.markdown(
                                "ΔH components — "
                                f"coh: {et.get('coherence_drop', 0):.4f}  •  "
                                f"anchor: {et.get('anchor_drop', 0):.4f}  •  "
                                f"ground: {et.get('ground_penalty', 0):.4f}"
                            )
                            if it.get("neighbors"):
                                st.caption("Top neighbors (weight)")
                                for n in it["neighbors"]:
                                    st.write(f"• {n['id']} — {n['w']:.3f}")
                with tabs[1]:
                    # Key diagnostic scalars
                    cols = st.columns(4)
                    cols[0].metric("ΔH total", f"{diag.get('deltaH_total', 0):.4f}")
                    cols[1].metric("Coherence fraction", f"{diag.get('coherence_fraction', 0):.3f}")
                    cols[2].metric("κ(M) bound", f"{diag.get('kappa_bound', 0):.3f}")
                    cols[3].metric("Scope ΔH diff", f"{diag.get('deltaH_scope_diff', 0):.3f}")
                    st.write("---")
                    st.json({k: v for k, v in diag.items() if k not in ("timings_ms",)})
                with tabs[2]:
                    st.info("Graph visualization TBD (local kNN + edge weights). Future: networkx + pyvis or d3 embed.")
                with tabs[3]:
                    timings = diag.get("timings_ms", {})
                    st.bar_chart({k: v for k, v in timings.items() if k != 'total'})
                    st.metric("Total ms", f"{timings.get('total', 0):.2f}")
                if show_raw:
                    st.write("---")
                    st.subheader("Raw JSON")
                    st.code(json.dumps(data, indent=2)[:100_000])
        except Exception as e:  # noqa: BLE001
            st.exception(e)
else:
    st.caption("Enter a query and click 'Run Search' to view coherence receipts.")

st.markdown(
    (
        "<hr />\n<small>Demo uses the mock connector unless remote API configured. "
        "Set CONSCIOUSDB_API env to point to a Cloud Run sandbox or other deployment.</small>"
    ),
    unsafe_allow_html=True,
)
