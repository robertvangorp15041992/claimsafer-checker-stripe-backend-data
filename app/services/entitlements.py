import os
import yaml
from app.models import Tier
from math import inf

_entitlements = None

ENTITLEMENTS_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "../entitlements.yaml"))

with open(ENTITLEMENTS_PATH, "r") as f:
    _entitlements = yaml.safe_load(f)
    if not _entitlements:
        raise RuntimeError("Entitlements YAML is empty or malformed!")

def get_entitlements(tier: Tier) -> dict:
    if _entitlements is None:
        raise RuntimeError("Entitlements not loaded!")
    return _entitlements.get(tier.value, {})

def max_daily_checks(tier: Tier) -> int:
    ent = get_entitlements(tier)
    val = ent.get("daily_checks", 0)
    if val == -1:
        return inf
    return val
