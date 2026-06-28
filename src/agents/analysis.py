"""
analysis.py - Agent #3.

Combines the structured situation (ingestion) with relevant company knowledge
(retrieval) and diagnoses what's going on, grounding findings in evidence.
It does NOT choose the action - that's the recommendation agent's job.

It also flags MISSING INFORMATION: facts that aren't present in the inputs but
would materially change the diagnosis or the recommended action. This makes the
"identify opportunities, risks, and missing information" step explicit.
"""
import json

from agents.base import Agent
from llm import chat_json


class AnalysisAgent(Agent):
    name = "analysis"

    def run(self, ingestion: dict, knowledge: dict) -> dict:
        system = (
            "You are an analysis agent for a SaaS Customer Success platform. "
            "Diagnose the customer's situation using ONLY the facts provided and "
            "the company playbooks supplied as context. Ground every finding in "
            "evidence. Also flag missing information - facts or context that are "
            "NOT available but would materially change the diagnosis or the "
            "recommended action. Do not recommend actions yet."
        )
        knowledge_text = "\n\n".join(
            f"[{h['source']} — {h['title']}]\n{h['text']}"
            for h in knowledge.get("hits", [])
        )
        prompt = f"""SITUATION (from ingestion):
{json.dumps(ingestion["summary"], indent=2)}

CUSTOMER FACTS:
{json.dumps(ingestion["record"], indent=2)}

RELEVANT COMPANY KNOWLEDGE:
{knowledge_text or "(none retrieved)"}

Return JSON with exactly these keys:
{{
  "situation_type": "churn_risk | upsell_opportunity | onboarding_gap | healthy | other",
  "urgency": "low | medium | high",
  "key_findings": [
    {{"finding": "...", "evidence": "which fact or playbook supports it"}}
  ],
  "risks": ["..."],
  "opportunities": ["..."],
  "missing_information": ["specific facts or context not available that would materially change the diagnosis or recommendation"],
  "playbooks_applied": ["the source files that informed this analysis"]
}}"""
        analysis = chat_json(prompt, system=system)
        analysis.setdefault("missing_information", [])  # always present downstream
        analysis["_inputs"] = {
            "customer_id": ingestion["customer_id"],
            "knowledge_sources": [h["source"] for h in knowledge.get("hits", [])],
        }
        return analysis