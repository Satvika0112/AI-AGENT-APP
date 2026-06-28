"""
planner.py - the orchestrator (dynamic plan + deterministic business rules).

Design: sense -> plan -> act.

  1. SENSE   Ingestion always runs first - perception, not a choice.
  2. PLAN    Deterministic BUSINESS RULES (domain.yaml) first; if none fire, an
             LLM PLANNING step picks which specialist agents to run and how deep
             to retrieve. Different customers take genuinely different routes.
  3. ACT     The Planner executes the chosen plan against a shared context and
             records a trace so the orchestration itself is explainable.

Extensibility:
  Agents are executed through a DISPATCH TABLE (self._handlers) keyed by agent
  name, not a hardcoded if/elif chain. Adding a new agent is additive: list it
  in domain.yaml (agents:), give it a dependency + canonical position + one-line
  description below, write the agent class, and register one handler. The
  execution loop never changes.

Guardrails:
  - Unknown step names returned by the LLM are dropped (and skipped if they
    somehow reach the loop without a handler).
  - Data dependencies are auto-repaired and run in a safe canonical order.
  - If planning fails or returns nothing usable, we fall back to the full
    pipeline - never worse than the old static behaviour.
"""
import json

from agents.ingestion import IngestionAgent
from agents.retrieval import RetrievalAgent
from agents.analysis import AnalysisAgent
from agents.recommendation import RecommendationAgent
from config import ALLOWED_AGENTS, DOMAIN, NEXT_BEST_ACTIONS
from llm import chat_json
import memory

# Agents the planner may schedule. Derived from domain.yaml (reusability story);
# ingestion is excluded because it's the fixed "sense" step that always runs.
PLANNABLE = [a for a in ALLOWED_AGENTS if a != "ingestion"]

# Canonical run order. Every dependency points "leftwards" here, so sorting a
# chosen step-set by this order automatically satisfies dependencies.
CANONICAL_ORDER = ["retrieval", "analysis", "recommendation"]

# Hard data dependencies: what must have run before each step.
DEPENDENCIES = {
    "retrieval": [],
    "analysis": [],                  # can run with OR without retrieved knowledge
    "recommendation": ["analysis"],  # needs an analysis to ground itself in
}

# Short descriptions handed to the planner so its choice is informed + explainable.
AGENT_DESCRIPTIONS = {
    "retrieval": "Pull relevant company playbooks / best-practice docs (RAG). "
                 "Skip only if the situation needs no organizational knowledge.",
    "analysis": "Diagnose the situation (churn risk / upsell / onboarding gap / "
                "healthy) grounded in the customer facts and any retrieved knowledge.",
    "recommendation": "Choose the next best action(s) from the catalogue, with "
                      "evidence and confidence. Requires analysis to have run first.",
}

# Deterministic business rules, loaded from domain.yaml (tunable without code).
BUSINESS_RULES = DOMAIN.get("business_rules", {})

# Signals that mean "this needs attention" - any blocks the healthy short-circuit.
ACTION_SIGNALS = {
    "champion_left", "usage_down", "competitor_mentioned", "low_seat_activation",
    "renewal_risk", "budget_pressure", "expansion_interest", "onboarding_gap",
    "feature_request", "support_issue",
}

# Canonical id -> label, so a recorded action always gets its proper label.
ACTION_LABELS = {a["id"]: a["label"] for a in NEXT_BEST_ACTIONS}


class Planner:
    def __init__(self):
        self.ingestion = IngestionAgent()
        self.retrieval = RetrievalAgent()
        self.analysis = AnalysisAgent()
        self.recommendation = RecommendationAgent()

        # Dispatch table: agent name -> handler. THIS is the extension point.
        # A handler takes (ingestion, ctx, plan), mutates the shared ctx, and
        # returns a short trace detail string. To add an agent, register it here.
        self._handlers = {
            "retrieval": self._do_retrieval,
            "analysis": self._do_analysis,
            "recommendation": self._do_recommendation,
        }

    # ---- step handlers (one per agent) -----------------------------------

    def _do_retrieval(self, ingestion: dict, ctx: dict, plan: dict) -> str:
        query = self._build_query(ingestion)
        ctx["knowledge"] = self.retrieval.run(query, k=plan["k"])
        return f"{len(ctx['knowledge']['hits'])} section(s), k={plan['k']}"

    def _do_analysis(self, ingestion: dict, ctx: dict, plan: dict) -> str:
        ctx["analysis"] = self.analysis.run(ingestion, ctx["knowledge"])
        return ctx["analysis"].get("situation_type", "?")

    def _do_recommendation(self, ingestion: dict, ctx: dict, plan: dict) -> str:
        signals = ingestion["summary"].get("signals", [])
        ctx["memory_hits"] = memory.recall_similar(                # learning loop
            situation_type=ctx["analysis"].get("situation_type", "other"),
            signals=signals,
        )
        ctx["recommendation"] = self.recommendation.run(
            ctx["analysis"], memory_hits=ctx["memory_hits"]
        )
        return f"{len(ctx['recommendation'].get('recommendations', []))} action(s)"

    # ---- helpers ---------------------------------------------------------

    @staticmethod
    def _build_query(ingestion: dict) -> str:
        s = ingestion["summary"]
        parts = [s.get("summary", "")]
        parts += s.get("signals", [])
        parts += s.get("customer_asks", [])
        return " ".join(p for p in parts if p) or ingestion["record"].get("notes", "")

    @staticmethod
    def _repair(requested: list) -> list:
        """Drop unknown steps, pull in dependencies, return a safe ordering."""
        needed = {s for s in requested if s in PLANNABLE}
        for s in list(needed):
            needed.update(d for d in DEPENDENCIES.get(s, []) if d in PLANNABLE)
        ordered = [s for s in CANONICAL_ORDER if s in needed]
        # Any plannable step not covered by the canonical order goes last,
        # preserving the planner's requested order (keeps the platform extensible).
        ordered += [s for s in requested if s in needed and s not in ordered]
        return ordered

    def _apply_rules(self, ingestion: dict):
        """Deterministic routing rules. Return a plan dict if one fires, else None."""
        rule = BUSINESS_RULES.get("healthy_account", {})
        if not rule.get("enabled", True):
            return None
        threshold = rule.get("min_health_score", 85)

        record = ingestion.get("record", {})
        summary = ingestion.get("summary", {})
        health = record.get("health_score")
        signals = {s.lower() for s in summary.get("signals", [])}
        asks = summary.get("customer_asks", [])
        sentiment = summary.get("sentiment", "")

        if (
            isinstance(health, (int, float))
            and health >= threshold
            and not (signals & ACTION_SIGNALS)
            and not asks
            and sentiment in {"positive", "neutral"}
        ):
            return {
                "steps": [],
                "k": 0,
                "reason": (
                    f"Business rule 'healthy_account': health {health} >= {threshold}, "
                    f"no action signals or open asks, sentiment {sentiment or 'n/a'} "
                    "- route to keep-monitoring."
                ),
                "fallback": False,
                "rule": "healthy_account",
            }
        return None

    def _make_plan(self, ingestion: dict, default_k: int) -> dict:
        """Pick a route: deterministic rules first, then the LLM planner."""
        ruled = self._apply_rules(ingestion)
        if ruled is not None:
            return ruled

        available = "\n".join(
            f"- {name}: {AGENT_DESCRIPTIONS.get(name, '')}" for name in PLANNABLE
        )
        system = (
            "You are the planner for a SaaS Customer Success decision platform. "
            "Ingestion has already read the interaction and produced the situation "
            "below. Decide which specialist agents to run, in what order, to reach a "
            "grounded next-best-action recommendation. Be efficient: only schedule "
            "what the situation actually needs. 'recommendation' requires 'analysis'. "
            "If the account looks healthy and the interaction needs no action, you may "
            "return an empty step list to keep monitoring."
        )
        prompt = f"""SITUATION (from ingestion):
{json.dumps(ingestion.get("summary", {}), indent=2)}

CUSTOMER FACTS:
{json.dumps(ingestion.get("record", {}), indent=2)}

AVAILABLE AGENTS (schedule any subset, in any order):
{available}

Return JSON with exactly these keys:
{{
  "steps": ["ordered subset of: {', '.join(PLANNABLE)}"],
  "k": 4,
  "reason": "one or two sentences: why this plan fits this situation"
}}"""
        try:
            plan = chat_json(prompt, system=system)
        except Exception:
            plan = {}

        if not isinstance(plan, dict):
            plan = {}
        steps = plan.get("steps")

        if steps is None or not isinstance(steps, list):
            return {
                "steps": list(CANONICAL_ORDER),
                "k": default_k,
                "reason": "Planner unavailable - defaulting to the full pipeline.",
                "fallback": True,
                "rule": None,
            }

        k = plan.get("k", default_k)
        try:
            k = max(1, min(8, int(k)))
        except (TypeError, ValueError):
            k = default_k

        return {
            "steps": self._repair(steps),
            "k": k,
            "reason": str(plan.get("reason", "")).strip(),
            "fallback": False,
            "rule": None,
        }

    # ---- main entry point ------------------------------------------------

    def run(self, customer_id: str, k: int = 4) -> dict:
        # 1. SENSE - always ingest first.
        ingestion = self.ingestion.run(customer_id)

        # 2. PLAN - deterministic rules first, then the LLM planner.
        plan = self._make_plan(ingestion, default_k=k)

        # 3. ACT - execute the chosen steps via the dispatch table.
        ctx = {
            "knowledge": {"query": "", "hits": []},
            "analysis": {},
            "memory_hits": [],
            "recommendation": {"recommendations": [], "requires_human_review": True},
        }
        trace = []
        if plan.get("rule"):
            trace.append({"step": f"rule:{plan['rule']}", "detail": "skipped pipeline"})

        for step in plan["steps"]:
            handler = self._handlers.get(step)
            if handler is None:
                # Plannable per config but no handler registered yet - skip safely.
                trace.append({"step": step, "detail": "no handler registered - skipped"})
                continue
            detail = handler(ingestion, ctx, plan)
            trace.append({"step": step, "detail": detail})

        # If no recommendation step ran (rule short-circuit or empty plan), record
        # an explicit 'hold' so the packet is always complete and explainable.
        if "recommendation" not in plan["steps"]:
            ctx["recommendation"] = {
                "recommendations": [{
                    "action_id": "hold",
                    "action_label": "No action yet - keep monitoring",
                    "rationale": plan.get("reason")
                    or "Planner determined the situation needs no action yet.",
                    "evidence": [],
                    "confidence": 0.5,
                    "priority": 1,
                }],
                "requires_human_review": True,
            }
            trace.append({"step": "hold", "detail": "no action scheduled"})

        return {
            "customer_id": customer_id,
            "ingestion": ingestion,
            "plan": {
                "steps": plan["steps"],
                "reason": plan["reason"],
                "rule": plan.get("rule"),
                "fallback": plan.get("fallback", False),
                "trace": trace,
            },
            "knowledge": ctx["knowledge"],
            "analysis": ctx["analysis"],
            "memory_hits": ctx["memory_hits"],
            "recommendation": ctx["recommendation"],
        }

    def record_decision(
        self, result: dict, action_id: str, decision: str, note: str = ""
    ) -> dict:
        """Persist a human decision back into memory (closes the learning loop)."""
        label = ACTION_LABELS.get(action_id, action_id)   # catalogue label as a baseline
        for rec in result["recommendation"].get("recommendations", []):
            if rec.get("action_id") == action_id:
                label = rec.get("action_label", label)     # prefer the recommended label
                break
        return memory.remember(
            customer_id=result["customer_id"],
            situation_type=result["analysis"].get("situation_type", "other"),
            action_id=action_id,
            action_label=label,
            decision=decision,
            signals=result["ingestion"]["summary"].get("signals", []),
            note=note,
        )