from .models import Tier

# Fill these with your real Stripe Price IDs!
PRICE_TO_TIER = {
    "price_123STARTER": Tier.starter,
    "price_456PRO": Tier.pro,
    "price_789ENTERPRISE": Tier.enterprise,
}
DEFAULT_TIER = Tier.starter

TIER_ORDER = [Tier.free, Tier.starter, Tier.pro, Tier.enterprise]

def tier_rank(tier: Tier) -> int:
    """Return the rank of a tier for comparison (higher is better)."""
    return TIER_ORDER.index(tier)
