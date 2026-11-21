"""Only takes trades that help it much more than its partner."""
from bohnanza import Bot


class TradeShark(Bot):
    description = "Trades only when it gains clearly more than its partner (partner's gain counts 80%)."
    details = ("Thinks in coins like the strategist, but drives a hard bargain: whatever a trade gives the "
               "partner counts 80% against it (150% if the partner leads; strategist 25% / 60%), and it wants a "
               "net gain of at least 0.2 coins. Fewer trades, but rarely a bad one.")
    HELP_WEIGHT = 0.8
    LEADER_HELP_WEIGHT = 1.5
    MIN_TRADE_GAIN = 0.2
