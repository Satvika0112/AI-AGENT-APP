"""
run.py - command-line entry point.

View decisions:
    python run.py                       # run every customer in data/customers.json
    python run.py acme                  # run one customer
    python run.py acme globex           # run several

Close the learning loop from the CLI (one customer at a time):
    python run.py acme --accept escalate --note "Exec call booked"
    python run.py initech --reject propose_upsell
    python run.py acme --edit schedule_checkin --note "Reframed as value review"

Prints a readable decision packet (including the dynamic PLAN the planner chose).
With a decision flag, the chosen action is written to shared memory via
Planner.record_decision() - the same path the UI uses - so future runs can
recall it. Without a flag, nothing is written (just like before).
"""
import sys
import json
import time
import argparse

from config import DATA_DIR
from run_pipeline import run_pipeline, get_planner


def _print_packet(result: dict) -> None:
    cid = result["customer_id"]
    name = result["ingestion"]["record"].get("name", cid)
    a = result["analysis"]
    print("=" * 70)
    print(f"CUSTOMER: {name} ({cid})")
    print("-" * 70)

    sit = a.get("situation_type")
    if sit:
        print(f"Situation : {sit}  |  urgency: {a.get('urgency')}")
    else:
        print("Situation : (not analysed - keep monitoring)")

    # --- the dynamic plan: what the planner decided to do and why ----------
    plan = result.get("plan", {})
    if plan:
        steps = plan.get("steps", [])
        route = " -> ".join(steps) if steps else "(hold - keep monitoring)"
        print(f"Plan      : {route}")
        if plan.get("reason"):
            print(f"  reason  : {plan['reason']}")
        if plan.get("rule"):
            print(f"  rule    : {plan['rule']} (deterministic business rule)")
        if plan.get("fallback"):
            print("  note    : planner fell back to the full pipeline")
        trace = plan.get("trace", [])
        if trace:
            print("  trace   :")
            for t in trace:
                print(f"    - {t.get('step')}: {t.get('detail')}")

    findings = a.get("key_findings", [])
    if findings:
        print("Findings  :")
        for f in findings:
            print(f"  - {f.get('finding')}")
            print(f"      evidence: {f.get('evidence')}")

    missing = a.get("missing_information", [])
    if missing:
        print("Missing   :")
        for m in missing:
            print(f"  - {m}")

    sources = sorted({h["source"] for h in result["knowledge"].get("hits", [])})
    if sources:
        print(f"Playbooks : {', '.join(sources)}")

    if result["memory_hits"]:
        print(f"Memory    : {len(result['memory_hits'])} similar past decision(s) recalled")

    print("Next best actions:")
    recs = result["recommendation"].get("recommendations", [])
    if not recs:
        print("  (none - keep monitoring)")
    for i, rec in enumerate(recs, 1):
        conf = rec.get("confidence")
        conf_s = f"{conf:.0%}" if isinstance(conf, (int, float)) else "n/a"
        print(f"  {i}. {rec.get('action_label')}  ({rec.get('action_id')})  [confidence {conf_s}]")
        print(f"     why: {rec.get('rationale')}")
    print(f"Human review required: {result['recommendation'].get('requires_human_review')}")
    print()


def _is_quota_error(err: Exception) -> bool:
    """True if the exception is a free-tier / rate-limit (429) quota error."""
    msg = str(err)
    return "RESOURCE_EXHAUSTED" in msg or "429" in msg


def _parse_args(argv):
    p = argparse.ArgumentParser(description="Run the Next Best Action pipeline.")
    p.add_argument("customers", nargs="*", help="customer ids (default: all)")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--accept", metavar="ACTION_ID", help="record an accepted decision")
    g.add_argument("--reject", metavar="ACTION_ID", help="record a rejected decision")
    g.add_argument("--edit", metavar="ACTION_ID", help="record an edited decision")
    p.add_argument("--note", default="", help="optional note stored with the decision")
    return p.parse_args(argv)


def main() -> None:
    args = _parse_args(sys.argv[1:])

    decision, action_id = None, None
    if args.accept:
        decision, action_id = "accepted", args.accept
    elif args.reject:
        decision, action_id = "rejected", args.reject
    elif args.edit:
        decision, action_id = "edited", args.edit

    if args.customers:
        customer_ids = args.customers
    else:
        customers = json.loads(
            (DATA_DIR / "customers.json").read_text(encoding="utf-8")
        )
        customer_ids = list(customers)

    # Recording is per-decision, so it needs exactly one customer.
    if decision and len(customer_ids) != 1:
        print("To record a decision, name exactly one customer, e.g.:")
        print('  python run.py acme --accept escalate --note "..."')
        return

    for i, cid in enumerate(customer_ids):
        try:
            result = run_pipeline(cid)
            _print_packet(result)

            if decision:
                rec_ids = {
                    r.get("action_id")
                    for r in result["recommendation"].get("recommendations", [])
                }
                if action_id not in rec_ids:
                    print(f"   note: '{action_id}' wasn't among the recommended "
                          "actions - recording it anyway.")
                get_planner().record_decision(result, action_id, decision, note=args.note)
                tail = f' ("{args.note}")' if args.note else ""
                print(f">> Recorded to memory: {action_id} = {decision}{tail}\n")

        except Exception as e:
            if _is_quota_error(e):
                print(
                    f"!! {cid}: hit the Gemini free-tier quota (429). "
                    "Run one customer at a time, switch to a lighter model in "
                    "llm.py, or wait for the midnight Pacific Time reset."
                )
                print("   Stopping here - the remaining customers would fail too.\n")
                break
            print(f"!! {cid}: {type(e).__name__}: {e}\n")

        if i < len(customer_ids) - 1:
            time.sleep(5)


if __name__ == "__main__":
    main()