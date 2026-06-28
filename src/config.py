"""
config.py - shared paths and domain configuration.
"""
from pathlib import Path
import yaml

SRC_DIR = Path(__file__).resolve().parent
ROOT_DIR = SRC_DIR.parent

DATA_DIR = ROOT_DIR / "data"
KNOWLEDGE_DIR = DATA_DIR / "knowledge"
INTERACTIONS_DIR = DATA_DIR / "interactions"
CONFIG_DIR = ROOT_DIR / "config"
DOMAIN_FILE = CONFIG_DIR / "domain.yaml"


def load_domain() -> dict:
    """Load the business-domain config (swap domain.yaml to change domains)."""
    with open(DOMAIN_FILE, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


DOMAIN = load_domain()
NEXT_BEST_ACTIONS = DOMAIN.get("next_best_actions", [])
ALLOWED_AGENTS = DOMAIN.get("agents", [])
SUCCESS_METRICS = DOMAIN.get("success_metrics", [])