"""Patient: grows long fields and protects them; trades only for clear gains."""
from bohnanza import Bot


class Hoarder(Bot):
    description = "Guards its fields hard (killing a young one costs it 2 coins) and trades only for clear gains."
    details = ("Thinks in coins like the strategist, but is picky: killing a field that pays nothing costs it "
               "2 coins (strategist 1), and it only trades when it gains at least 0.4 coins (strategist 0.05). "
               "Aims for big harvests at the risk of being stuck with cards nobody will trade for.")
    CHURN_PENALTY = 2.0
    MIN_TRADE_GAIN = 0.4
