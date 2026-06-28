"""
app.py - the human-in-the-loop UI (and where the learning loop closes).

    streamlit run src/app.py

What it does:
  - Pick a customer, run the planner, and see the decision packet: the dynamic
    plan the planner chose, the analysis + evidence, and the recommended next
    best actions with confidence.
  - A human Accepts / Edits / Rejects each recommendation. That decision is
    written to shared memory (data/memory.json) via Planner.record_decision().
  - On later runs, similar past decisions are recalled and shown - so you can
    watch the system learn from real choices instead of starting cold.

The pipeline is only run on the "Analyze" button and cached in session state, so
clicking Accept/Reject does NOT re-run the (LLM-backed) pipeline.
"""
import os
import sys

# Make src/ importable whether you launch from the repo root or from src/.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import json

import streamlit as st

from config import DATA_DIR
import memory

st.set_page_config(page_title="Next Best Action", page_icon="🎯", layout="wide")


# --- cached resources -------------------------------------------------------

@st.cache_resource
def get_planner():
    """Build the Planner once (its retrieval index is built lazily on first run)."""
    from planner import Planner  # imported lazily so the app still loads without a key
    return Planner()


@st.cache_data
def load_customers() -> dict:
    return json.loads((DATA_DIR / "customers.json").read_text(encoding="utf-8"))


def save_decision(result: dict, action_id: str, decision: str, note: str) -> None:
    """Persist a human decision to shared memory and remember it in this session."""
    get_planner().record_decision(result, action_id, decision, note=note)
    st.session_state.setdefault("saved", {})[action_id] = (
        decision + (f" — {note}" if note else "")
    )
    st.rerun()


# --- sidebar: choose a customer and run -------------------------------------

customers = load_customers()
ids = list(customers)

with st.sidebar:
    st.title("🎯 Next Best Action")
    st.caption("Agentic decision intelligence for Customer Success.")
    cid = st.selectbox(
        "Customer",
        ids,
        format_func=lambda c: f"{customers[c]['name']}  ·  {c}",
    )
    k = st.slider("Retrieval depth (k)", 1, 8, 4,
                  help="How many knowledge sections the retrieval step may pull.")
    run = st.button("Analyze", type="primary", use_container_width=True)
    st.caption("Each run makes a few calls to the free Gemini tier.")

if run:
    with st.spinner(f"Planning the next best action for {customers[cid]['name']}…"):
        try:
            st.session_state.result = get_planner().run(cid, k=k)
            st.session_state.saved = {}  # reset per-recommendation decision flags
        except Exception as e:
            st.session_state.result = None
            st.error(
                f"The pipeline couldn't finish: {e}\n\n"
                "If this is a quota error, run one customer at a time or wait for "
                "the free-tier reset. If it's a missing key, set GEMINI_API_KEY in .env."
            )


# --- main panel -------------------------------------------------------------

result = st.session_state.get("result")

if not result:
    st.title("Pick a customer and Analyze")
    st.write(
        "Choose an account in the sidebar and click **Analyze**. You'll get the "
        "planner's chosen route, the diagnosis with evidence, and recommended "
        "actions you can accept, edit, or reject."
    )
    st.stop()

analysis = result["analysis"]
plan = result["plan"]
rec_block = result["recommendation"]
name = result["ingestion"]["record"].get("name", result["customer_id"])

st.title(name)

c1, c2, c3 = st.columns(3)
c1.metric("Situation", analysis.get("situation_type") or "not analysed")
c2.metric("Urgency", analysis.get("urgency") or "—")
c3.metric("Past decisions recalled", len(result["memory_hits"]))

# Plan card: what the planner decided to do, and why.
with st.container(border=True):
    steps = plan.get("steps", [])
    route = " → ".join(steps) if steps else "hold — keep monitoring"
    st.markdown(f"**Planner route:**  {route}")
    if plan.get("rule"):
        st.markdown(f"🔧 Deterministic rule fired: `{plan['rule']}`")
    if plan.get("fallback"):
        st.warning("The LLM planner was unavailable, so it ran the full pipeline.")
    if plan.get("reason"):
        st.caption(plan["reason"])
    if plan.get("trace"):
        with st.expander("Execution trace"):
            for t in plan["trace"]:
                st.write(f"- **{t.get('step')}** — {t.get('detail')}")

# Analysis + evidence.
findings = analysis.get("key_findings", [])
if findings:
    with st.expander(f"Analysis — {len(findings)} finding(s) with evidence"):
        for f in findings:
            st.markdown(f"**{f.get('finding')}**")
            st.caption(f"Evidence: {f.get('evidence')}")

sources = sorted({h["source"] for h in result["knowledge"].get("hits", [])})
if sources:
    st.caption("Playbooks consulted: " + ", ".join(sources))

# The learning loop, made visible.
if result["memory_hits"]:
    with st.expander(
        f"🧠 {len(result['memory_hits'])} similar past decision(s) informed this",
        expanded=True,
    ):
        for m in result["memory_hits"]:
            line = (
                f"- {m.get('situation_type')} → **{m.get('action_label')}** "
                f"({m.get('decision')})"
            )
            if m.get("note"):
                line += f" — {m['note']}"
            st.write(line)

st.divider()
st.subheader("Recommended next best actions")
if rec_block.get("requires_human_review"):
    st.info("A human reviews these before anything is sent.")

recs = rec_block.get("recommendations", [])
if not recs:
    st.write("No action for now — keep monitoring.")

saved = st.session_state.get("saved", {})

for idx, rec in enumerate(recs):
    aid = rec.get("action_id")
    with st.container(border=True):
        head_l, head_r = st.columns([5, 1])
        head_l.markdown(f"### {rec.get('action_label')}")
        conf = rec.get("confidence")
        if isinstance(conf, (int, float)):
            head_r.markdown(f"**{conf:.0%}**")
            head_r.caption("confidence")

        if rec.get("rationale"):
            st.write(rec["rationale"])

        evidence = rec.get("evidence") or []
        if evidence:
            with st.expander("Evidence"):
                for e in evidence:
                    st.write(f"- {e}")

        if aid in saved:
            st.success(f"Recorded: {saved[aid]}")
        else:
            note = st.text_input(
                "Note (optional)",
                key=f"note_{aid}_{idx}",
                placeholder="Why you're accepting, editing, or rejecting this",
            )
            b1, b2, b3 = st.columns(3)
            if b1.button("Accept", key=f"acc_{aid}_{idx}", use_container_width=True):
                save_decision(result, aid, "accepted", note)
            if b2.button("Edit", key=f"edt_{aid}_{idx}", use_container_width=True):
                save_decision(result, aid, "edited", note)
            if b3.button("Reject", key=f"rej_{aid}_{idx}", use_container_width=True):
                save_decision(result, aid, "rejected", note)

# Shared decision history (the contents of memory.json).
st.divider()
with st.expander("📜 Decision history (shared memory)"):
    records = memory.all_records()
    if not records:
        st.caption("No decisions recorded yet. Accept or reject an action above to start the loop.")
    else:
        st.caption(f"{len(records)} decision(s) recorded. Newest first.")
        for r in reversed(records[-50:]):
            stamp = r.get("timestamp", "")[:19].replace("T", " ")
            line = (
                f"- `{stamp}` · **{r.get('customer_id')}** · "
                f"{r.get('situation_type')} → {r.get('action_label')} "
                f"(**{r.get('decision')}**)"
            )
            if r.get("note"):
                line += f" — {r['note']}"
            st.write(line)