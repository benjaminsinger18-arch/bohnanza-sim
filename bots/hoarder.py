"""Patient: grows long fields and protects them; trades only for clear gains."""
from bohnanza import Bot


class Hoarder(Bot):
    description = "Patient: counts 97% of future growth, guards fields hard, trades only for clear gains."
    details = ("Thinks in coins like the strategist, but bets on growth: a field's future counts at 97% "
               "(strategist 85%), killing a field that pays nothing costs it 2 coins (strategist 1), and it only "
               "trades when it gains at least 0.4 coins. Aims for big harvests at the risk of being stuck.")
    RISK_DISCOUNT = 0.97
    CHURN_PENALTY = 2.0
    MIN_TRADE_GAIN = 0.4
