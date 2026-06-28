"""
recommendation.py - Agent #4.

Turns the analysis into concrete next best actions, chosen ONLY from the
catalogue in config/domain.yaml. Each recommendation carries supporting
evidence and a confidence score, and the human always stays in the loop.
"""
import json

from agents.base import Agent
from config import NEXT_BEST_ACTIONS
from llm import chat_json


class RecommendationAgent(Agent):
    name = "recommendation"

    def run(self, analysis: dict, memory_hits: list = None) -> dict:
        memory_hits = memory_hits or []

        catalogue = "\n".join(
            f"- {a['id']}: {a['label']}" for a in NEXT_BEST_ACTIONS
        )
        memory_text = "\n".join(
            f"- {m.get('situation_type')} -> {m.get('action_id')} "
            f"({m.get('decision')})" + (f": {m['note']}" if m.get("note") else "")
            for m in memory_hits
        ) or "(no similar past decisions yet)"

        system = (
            "You are a recommendation agent for a SaaS Customer Success platform. "
            "Choose the next best action(s) ONLY from the allowed catalogue. Ground "
            "each recommendation in the analysis evidence. Prefer the smallest set "
            "of high-impact actions. A human will review your output before anything "
            "is sent."
        )
        prompt = f"""ANALYSIS:
{json.dumps(analysis, indent=2)}

ALLOWED ACTIONS (use only these ids):
{catalogue}

SIMILAR PAST DECISIONS (learning loop, may be empty):
{memory_text}

Return JSON with exactly these keys:
{{
  "recommendations": [
    {{
      "action_id": "one of the allowed ids",
      "action_label": "the matching label",
      "rationale": "why this action, tied to the analysis evidence",
      "evidence": ["specific facts or findings that support it"],
      "confidence": 0.0,
      "priority": 1
    }}
  ],
  "requires_human_review": true
}}"""
        result = chat_json(prompt, system=system)

        # Guardrail: drop any action the model invented outside the catalogue,
        # and force the canonical label so the UI stays consistent.
        valid = {a["id"]: a["label"] for a in NEXT_BEST_ACTIONS}
        cleaned = []
        for rec in result.get("recommendations", []):
            aid = rec.get("action_id")
            if aid in valid:
                rec["action_label"] = valid[aid]
                cleaned.append(rec)
        cleaned.sort(key=lambda r: r.get("priority", 99))
        result["recommendations"] = cleaned
        result["requires_human_review"] = True  # non-negotiable
        return result