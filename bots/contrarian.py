"""Avoids beans other players are already growing (less competition for the copies left)."""
from bohnanza import Bot


class Contrarian(Bot):
    description = "Avoids beans opponents are growing: expects 30% fewer copies for each rival field."
    details = ("Thinks in coins like the strategist, but knows it has to share: for every opponent field "
               "holding a bean, it expects to collect 30% fewer of the copies still out there (never below "
               "25%). So it starts fields in beans nobody else is collecting and sells contested ones sooner.")
    RIVAL_CUT = 0.3

    def available(self, view, bean):
        c = self._ctx(view)
        if "rivals" not in c:
            r = {}
            for o in view.opponents:
                for b, n in o.fields:
                    if b:
                        r[b] = r.get(b, 0) + 1
            c["rivals"] = r
        share = max(0.25, 1.0 - self.RIVAL_CUT * c["rivals"].get(bean, 0))
        return super().available(view, bean) * share
