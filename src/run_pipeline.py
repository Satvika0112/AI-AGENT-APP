"""
run_pipeline.py - the single library entry point.

Other code (the CLI in run.py, the future Streamlit UI) imports run_pipeline()
to get a decision packet for one customer. The Planner is built lazily and
cached so the vector index is only created once per process.
"""
from planner import Planner

_planner = None


def get_planner() -> Planner:
    global _planner
    if _planner is None:
        _planner = Planner()
    return _planner


def run_pipeline(customer_id: str, k: int = 4) -> dict:
    """Run the full pipeline for one customer and return the decision packet."""
    return get_planner().run(customer_id, k=k)