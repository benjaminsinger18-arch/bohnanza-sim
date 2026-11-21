"""Avoids beans other players are already growing (less competition for the copies left)."""
from bohnanza import Bot


class Contrarian(Bot):
    description = "Strongly avoids beans opponents are growing: expects 60% fewer copies per rival field (strategist 30%)."
    details = ("Thinks in coins like the strategist, but takes competition much more seriously: for every "
               "opponent field holding a bean, it expects to collect 60% fewer of the copies still out there "
               "(never below 25%; strategist 30%). So it starts fields in beans nobody else is collecting and sells contested "
               "ones sooner.")
    RIVAL_CUT = 0.6
