"""
2_evaluation.py - the Evaluation page of the Streamlit app.

Two things live here:

  1. DECISION QUALITY (free, instant)
     Reads the human decisions recorded in memory.json and turns them into the
     numbers that show whether the platform's recommendations are trusted:
     acceptance rate, edit rate, rejection rate, and breakdowns by situation and
     by action. No LLM calls - it just reads the learning loop.

  2. OFFLINE ACCURACY (opt-in, makes LLM calls)
     Runs the planner over a small labelled "golden set" of the seed customers
     and grades whether it reaches the expected situation + action. It costs a
     few Gemini calls per customer, so it's behind a button and runs one at a
     time to stay friendly to the free tier.
"""
import os
import sys
import time
import json

# Make src/ importable whether the app was opened here directly or from the home
# page. This page lives in src/pages/, so src/ is two directories up.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st

from config import DATA_DIR
import memory
import metrics

st.set_page_config(page_title="Evaluation", page_icon="📊", layout="wide")

st.title("📊 Evaluation")
st.caption(
    "How well is the platform doing? The top half reads real human decisions "
    "from the learning loop. The bottom half grades the planner against a small "
    "set of known-answer cases."
)


def _load_customers() -> dict:
    return json.loads((DATA_DIR / "customers.json").read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# 1. Decision quality (from memory.json) - no LLM calls
# ---------------------------------------------------------------------------
st.header("Decision quality (from the learning loop)")

records = memory.all_records()
summary = metrics.decision_summary(records)

if summary["total"] == 0:
    st.info(
        "No decisions recorded yet. Go to the main page, **Analyze** a customer, "
        "and Accept / Edit / Reject some recommendations — then come back here."
    )
else:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Decisions recorded", summary["total"])
    c2.metric("Accepted as-is", f"{summary['acceptance_rate']:.0%}",
              help="Share accepted without edits. A proxy for recommendation quality.")
    c3.metric("Accepted or edited", f"{summary['useful_rate']:.0%}",
              help="An edited recommendation was still a useful starting point.")
    c4.metric("Rejected", summary["rejected"])

    st.subheader("By situation type")
    st.dataframe(metrics.breakdown_rows(records, "situation_type"),
                 use_container_width=True, hide_index=True)

    st.subheader("By recommended action")
    st.dataframe(metrics.breakdown_rows(records, "action_label"),
                 use_container_width=True, hide_index=True)

st.divider()

# ---------------------------------------------------------------------------
# 2. Offline accuracy against a golden set (opt-in, LLM calls)
# ---------------------------------------------------------------------------
st.header("Offline accuracy (golden set)")
st.caption(
    "Runs the full planner for each labelled customer and checks the detected "
    "situation and top recommended action against the expected answer. Makes a "
    "few Gemini calls per customer, so it runs one at a time."
)

customers = _load_customers()
gold = metrics.GOLDEN_SET
gradable = [cid for cid in gold if cid in customers]

st.write("**Golden set:** " + (", ".join(gradable) or "(none match customers.json)"))
st.caption(
    "These expected answers are editable in `metrics.GOLDEN_SET` — tune them if "
    "you disagree with a label."
)

if st.button("Run accuracy check", type="primary", disabled=not gradable):
    from run_pipeline import run_pipeline  # lazy import: needs GEMINI_API_KEY

    rows, sit_hits, act_hits = [], 0, 0
    progress = st.progress(0.0, text="Starting…")

    for i, cid in enumerate(gradable):
        progress.progress(i / len(gradable), text=f"Evaluating {cid}…")
        try:
            result = run_pipeline(cid)
            graded = metrics.grade_result(result, gold[cid])
        except Exception as e:
            msg = str(e)
            if "RESOURCE_EXHAUSTED" in msg or "429" in msg:
                st.warning(
                    f"Hit the Gemini free-tier quota on '{cid}'. Stopping here — "
                    "wait for the reset and run it again."
                )
                break
            st.error(f"{cid}: {type(e).__name__}: {e}")
            continue

        sit_hits += int(graded["situation_ok"])
        act_hits += int(graded["action_ok"])
        rows.append({
            "customer": customers[cid]["name"],
            "expected situation": graded["expected_situation"],
            "detected": graded["detected_situation"] or "—",
            "situation": "✅" if graded["situation_ok"] else "❌",
            "expected action": graded["expected_action"],
            "top action": graded["top_action"] or "—",
            "action": "✅" if graded["action_ok"] else "❌",
        })

        if i < len(gradable) - 1:
            time.sleep(5)  # be gentle on the free tier

    progress.empty()

    if rows:
        n = len(rows)
        a1, a2 = st.columns(2)
        a1.metric("Situation accuracy", f"{sit_hits / n:.0%}", f"{sit_hits}/{n} correct")
        a2.metric("Action accuracy", f"{act_hits / n:.0%}", f"{act_hits}/{n} correct")
        st.dataframe(rows, use_container_width=True, hide_index=True)