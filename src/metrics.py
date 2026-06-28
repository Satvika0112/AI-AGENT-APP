"""
metrics.py - pure functions that turn the decision history (memory.json) and
golden-set runs into the numbers shown on the Evaluation page.

There is deliberately NO Streamlit in here, so these stay easy to test, reuse,
and reason about. The Evaluation page (src/pages/2_evaluation.py) imports these
and just handles display.
"""
from collections import Counter


# What we EXPECT the platform to conclude for each seed customer. This is the
# small "golden set" the offline accuracy check grades against. It's labels, not
# code - edit it freely as the data or your judgement changes.
GOLDEN_SET = {
    "acme":    {"situation_type": "churn_risk",         "action_id": "escalate"},
    "globex":  {"situation_type": "upsell_opportunity", "action_id": "propose_upsell"},
    "initech": {"situation_type": "onboarding_gap",     "action_id": "offer_training"},
    "hooli":   {"situation_type": "healthy",            "action_id": "hold"},
}


# ---------------------------------------------------------------------------
# Decision quality (over the human decisions stored in memory.json)
# ---------------------------------------------------------------------------

def decision_summary(records: list) -> dict:
    """Headline numbers across all recorded human decisions."""
    total = len(records)
    by_decision = Counter(r.get("decision") for r in records)
    accepted = by_decision.get("accepted", 0)
    edited = by_decision.get("edited", 0)
    rejected = by_decision.get("rejected", 0)
    useful = accepted + edited  # an edited rec was still a useful starting point
    return {
        "total": total,
        "accepted": accepted,
        "edited": edited,
        "rejected": rejected,
        "acceptance_rate": (accepted / total) if total else 0.0,
        "useful_rate": (useful / total) if total else 0.0,
    }


def breakdown_rows(records: list, key: str) -> list:
    """Group decisions by a record field (e.g. 'situation_type', 'action_label')
    and return rows ready to drop into st.dataframe, busiest group first."""
    groups: dict[str, Counter] = {}
    for r in records:
        label = r.get(key) or "?"
        groups.setdefault(label, Counter())[r.get("decision", "?")] += 1

    rows = []
    for label, counts in sorted(groups.items(), key=lambda kv: -sum(kv[1].values())):
        total = sum(counts.values())
        rows.append({
            key: label,
            "total": total,
            "accepted": counts.get("accepted", 0),
            "edited": counts.get("edited", 0),
            "rejected": counts.get("rejected", 0),
            "accept rate": f"{(counts.get('accepted', 0) / total):.0%}" if total else "0%",
        })
    return rows


# ---------------------------------------------------------------------------
# Offline accuracy (grade a planner result against the golden set)
# ---------------------------------------------------------------------------

def _situation_of(result: dict) -> str | None:
    """The effective situation type for grading.

    When the deterministic 'healthy_account' rule fires, the planner short-circuits
    and never runs the analysis agent, so analysis.situation_type is absent. We
    treat that fired rule as situation 'healthy' so the golden set can grade it.
    """
    sit = result.get("analysis", {}).get("situation_type")
    if not sit and result.get("plan", {}).get("rule") == "healthy_account":
        return "healthy"
    return sit


def grade_result(result: dict, expected: dict) -> dict:
    """Compare one planner result against its expected (situation, action)."""
    detected_situation = _situation_of(result)
    recs = result.get("recommendation", {}).get("recommendations", [])
    top_action = recs[0].get("action_id") if recs else None

    return {
        "expected_situation": expected.get("situation_type"),
        "detected_situation": detected_situation,
        "situation_ok": detected_situation == expected.get("situation_type"),
        "expected_action": expected.get("action_id"),
        "top_action": top_action,
        "action_ok": top_action == expected.get("action_id"),
    }