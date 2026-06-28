"""
ingestion.py - Agent #1.

Reads a raw customer interaction (email, call transcript, CSM notes) together
with the structured customer record, and turns them into a clean structured
"situation" the rest of the pipeline can reason over. It only captures what is
present - it does NOT diagnose or recommend.
"""
import json
from pathlib import Path

from agents.base import Agent
from config import DATA_DIR, INTERACTIONS_DIR
from llm import chat_json

CUSTOMERS_FILE = DATA_DIR / "customers.json"


def _load_customers() -> dict:
    with open(CUSTOMERS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


class IngestionAgent(Agent):
    name = "ingestion"

    def run(self, customer_id: str, interaction_path: str = None) -> dict:
        customers = _load_customers()
        if customer_id not in customers:
            raise ValueError(
                f"Unknown customer_id '{customer_id}'. Known: {', '.join(customers)}"
            )
        record = customers[customer_id]

        # Auto-discover the interaction file (e.g. acme_call.txt) if not given.
        if interaction_path is None:
            matches = sorted(INTERACTIONS_DIR.glob(f"{customer_id}_*"))
            if not matches:
                raise FileNotFoundError(
                    f"No interaction file for '{customer_id}' in {INTERACTIONS_DIR}"
                )
            interaction_path = matches[0]
        interaction_text = Path(interaction_path).read_text(encoding="utf-8")

        system = (
            "You are an ingestion agent for a SaaS Customer Success platform. "
            "Read the raw customer interaction and the customer record and extract "
            "a clean, factual structured summary. Do not diagnose or recommend - "
            "only capture what is present."
        )
        prompt = f"""CUSTOMER RECORD:
{json.dumps(record, indent=2)}

RAW INTERACTION:
{interaction_text}

Return JSON with exactly these keys:
{{
  "customer_id": "{customer_id}",
  "channel": "email | call | notes | other",
  "summary": "2-3 sentence neutral summary of the interaction",
  "customer_asks": ["explicit requests the customer made, if any"],
  "signals": ["short keyword signals, e.g. 'champion_left', 'usage_down', 'competitor_mentioned', 'expansion_interest', 'low_seat_activation'"],
  "sentiment": "positive | neutral | negative | mixed"
}}"""
        summary = chat_json(prompt, system=system)

        return {
            "customer_id": customer_id,
            "record": record,
            "summary": summary,
            "interaction_path": str(interaction_path),
        }