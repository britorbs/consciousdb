from __future__ import annotations

"""Basic batch_query behavior tests."""


def test_batch_query_returns_list(stub_client):
    qs = ["q1", "q2", "q3"]
    out = stub_client.batch_query(qs, k=2, m=5)
    assert len(out) == len(qs)
    for res in out:
        assert len(res.items) == 2
        assert res.diagnostics.get("deltaH_total") == 0.0
