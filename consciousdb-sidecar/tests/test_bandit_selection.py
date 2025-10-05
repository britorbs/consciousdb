from fastapi.testclient import TestClient
from api.main import app, SET
from adaptive.manager import STATE

def test_bandit_selection_and_reward(monkeypatch):
    SET.enable_adaptive = True
    SET.enable_bandit = True
    # ensure bandit enabled in state
    STATE.bandit_enabled = True
    client = TestClient(app)
    # issue a few queries to pull initial arms
    qids = []
    for _ in range(4):
        r = client.post("/query", json={"query":"bandit test", "k":4, "m":140, "overrides": {"alpha_deltaH": 0.1}})
        assert r.status_code == 200
        qids.append(r.json().get("query_id"))
    # Provide feedback marking some as positive
    pos = 0
    for qid in qids:
        r = client.post("/feedback", json={"query_id": qid, "clicked_ids": ["doc1"], "accepted_id": None})
        assert r.status_code == 200
        pos += 1
    # After feedback, at least one arm should have non-zero reward_sum
    rewards = [arm.reward_sum for arm in STATE.bandit_arms]
    assert any(r > 0 for r in rewards)
