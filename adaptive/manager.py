"""Adaptive parameter manager (scaffold).

Provides a minimal in-memory heuristic for suggesting `alpha_deltaH`:
- Tracks recent feedback events containing: coherence_drop_total (deltaH_total), redundancy, clicked / accepted signals.
- Computes a moving correlation between deltaH_total and positive feedback.
- Suggests nudging alpha upward if positive correlation high; downward if negative.

Design notes:
- Stateless across process restarts (future: pluggable persistence layer).
- Thread safety: naive; FastAPI default workers (single-thread) fine for scaffold.
- Feature-gated via `ENABLE_ADAPTIVE` in settings; no-op if disabled.
"""

from __future__ import annotations

import json
import math
import os
import tempfile
from dataclasses import dataclass, field

MAX_EVENTS = 200  # ring buffer limit
MIN_SAMPLE = 15
DEFAULT_BANDIT_ARMS = [0.05, 0.1, 0.15, 0.2, 0.25, 0.3]


@dataclass
class BanditArm:
    alpha: float
    pulls: int = 0
    reward_sum: float = 0.0  # cumulative reward (0/1 or fractional)

    @property
    def avg_reward(self) -> float:
        return self.reward_sum / self.pulls if self.pulls > 0 else 0.0


@dataclass
class FeedbackEvent:
    deltaH_total: float
    redundancy: float
    positive: bool  # derived from accepted/clicked


@dataclass
class AdaptiveState:
    events: list[FeedbackEvent] = field(default_factory=list)
    suggested_alpha: float | None = None
    last_computed_on: int = 0  # simple counter of events
    # Bandit
    bandit_arms: list[BanditArm] = field(default_factory=lambda: [BanditArm(a) for a in DEFAULT_BANDIT_ARMS])
    bandit_enabled: bool = False
    bandit_query_arm: dict[str, float] = field(
        default_factory=dict
    )  # query_id -> alpha chosen (for reward attribution)

    def add(self, evt: FeedbackEvent):
        self.events.append(evt)
        if len(self.events) > MAX_EVENTS:
            self.events.pop(0)

    def compute(self):
        n = len(self.events)
        if n < MIN_SAMPLE:
            self.suggested_alpha = None
            return
        # Compute point-biserial like correlation between deltaH_total and positive
        xs = [e.deltaH_total for e in self.events]
        ys = [1.0 if e.positive else 0.0 for e in self.events]
        mean_x = sum(xs) / n
        mean_y = sum(ys) / n
        cov = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys)) / (n - 1 or 1)
        var_x = sum((x - mean_x) ** 2 for x in xs) / (n - 1 or 1)
        var_y = sum((y - mean_y) ** 2 for y in ys) / (n - 1 or 1)
        if var_x <= 1e-9 or var_y <= 1e-9:
            self.suggested_alpha = None
            return
        corr = cov / math.sqrt(var_x * var_y)
        # Map correlation [-1,1] into adjustment around base 0.1 within [0.02,0.5]
        base = 0.1
        span = 0.2  # magnitude around base
        adj = base + span * corr
        self.suggested_alpha = float(min(0.5, max(0.02, adj)))


STATE = AdaptiveState()
# Query diagnostics cache: query_id -> (deltaH_total, redundancy)
QUERY_CACHE: dict[str, tuple[float, float]] = {}
QUERY_CACHE_MAX = 500


def record_feedback(deltaH_total: float, redundancy: float, clicked: int, accepted: bool):
    positive = accepted or clicked > 0
    evt = FeedbackEvent(deltaH_total=deltaH_total, redundancy=redundancy, positive=positive)
    STATE.add(evt)
    # Recompute every 5 new events for cheapness
    if len(STATE.events) - STATE.last_computed_on >= 5:
        STATE.compute()
        STATE.last_computed_on = len(STATE.events)


def get_suggested_alpha() -> float | None:
    return STATE.suggested_alpha


def cache_query(query_id: str, deltaH_total: float, redundancy: float):
    QUERY_CACHE[query_id] = (deltaH_total, redundancy)
    if len(QUERY_CACHE) > QUERY_CACHE_MAX:
        # simple FIFO pruning: pop oldest inserted key
        try:
            oldest = next(iter(QUERY_CACHE.keys()))
            QUERY_CACHE.pop(oldest, None)
        except StopIteration:  # pragma: no cover
            pass


def lookup_query(query_id: str) -> tuple[float, float] | None:
    return QUERY_CACHE.get(query_id)


def save_state(path: str) -> None:
    try:
        data = {
            "suggested_alpha": STATE.suggested_alpha,
            "events": [
                {"deltaH_total": e.deltaH_total, "redundancy": e.redundancy, "positive": e.positive}
                for e in STATE.events
            ],
            "bandit": {
                "arms": [
                    {"alpha": arm.alpha, "pulls": arm.pulls, "reward_sum": arm.reward_sum} for arm in STATE.bandit_arms
                ]
            },
        }
        tmp_fd, tmp_path = tempfile.mkstemp(prefix="adaptive_state_", suffix=".json")
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
            json.dump(data, f)
        os.replace(tmp_path, path)
    except Exception:
        pass  # best-effort; no logging here to avoid circular imports


def load_state(path: str) -> None:
    if not os.path.exists(path):
        return
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        STATE.events.clear()
        for raw in data.get("events", [])[-MAX_EVENTS:]:
            STATE.events.append(
                FeedbackEvent(
                    deltaH_total=float(raw.get("deltaH_total", 0.0)),
                    redundancy=float(raw.get("redundancy", 0.0)),
                    positive=bool(raw.get("positive", False)),
                )
            )
        STATE.suggested_alpha = data.get("suggested_alpha")
        STATE.last_computed_on = len(STATE.events)
        # Load bandit arms if present
        braw = data.get("bandit", {})
        arms_raw = braw.get("arms")
        if arms_raw:
            STATE.bandit_arms = []
            for ar in arms_raw:
                try:
                    STATE.bandit_arms.append(
                        BanditArm(
                            alpha=float(ar.get("alpha")),
                            pulls=int(ar.get("pulls", 0)),
                            reward_sum=float(ar.get("reward_sum", 0.0)),
                        )
                    )
                except Exception:
                    continue
    except Exception:
        STATE.events.clear()
        STATE.suggested_alpha = None
        STATE.last_computed_on = 0


# ---------------- Bandit (UCB1) -----------------
def bandit_select(query_id: str) -> float | None:
    """Select an alpha arm via UCB1. Returns alpha or None if disabled.

    Must have STATE.bandit_enabled set externally (e.g., from settings) before calling.
    """
    if not STATE.bandit_enabled:
        return None
    arms = STATE.bandit_arms
    if not arms:  # defensive guard: no arms configured
        return None
    # Ensure at least one pull for each arm (initial exploration)
    for arm in arms:
        if arm.pulls == 0:
            arm.pulls += 1
            STATE.bandit_query_arm[query_id] = arm.alpha
            return arm.alpha
    total_pulls = sum(a.pulls for a in arms)
    import math as _m

    best_alpha: float | None = None
    best_score = -1e9
    for arm in arms:
        ucb = arm.avg_reward + (2.0 * (_m.log(total_pulls) / arm.pulls)) ** 0.5
        if ucb > best_score:
            best_score = ucb
            best_alpha = arm.alpha
    # Record selection
    for arm in arms:
        if arm.alpha == best_alpha:
            arm.pulls += 1
            break
    if best_alpha is None:
        return None
    STATE.bandit_query_arm[query_id] = best_alpha
    # Simple eviction of old query_ids to prevent unbounded growth
    if len(STATE.bandit_query_arm) > 2000:
        try:
            oldest = next(iter(STATE.bandit_query_arm.keys()))
            STATE.bandit_query_arm.pop(oldest, None)
        except StopIteration:
            pass
    return best_alpha


def bandit_record_reward(query_id: str, reward: float) -> None:
    if not STATE.bandit_enabled:
        return
    alpha = STATE.bandit_query_arm.get(query_id)
    if alpha is None:
        return
    for arm in STATE.bandit_arms:
        if arm.alpha == alpha:
            arm.reward_sum += reward
            break
