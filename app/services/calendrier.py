import datetime as dt

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import JourFerie

MOIS_FR = ["janvier", "février", "mars", "avril", "mai", "juin",
           "juillet", "août", "septembre", "octobre", "novembre", "décembre"]


def charger_feries(db: Session) -> set[dt.date]:
    return set(db.scalars(select(JourFerie.date)))


def est_ouvrable(d: dt.date, feries: set[dt.date]) -> bool:
    return d.weekday() < 5 and d not in feries


def jours_ouvrables(debut: dt.date, fin: dt.date, feries: set[dt.date]) -> int:
    """Équivalent de NETWORKDAYS(debut, fin, feries) : bornes incluses, lun-ven hors fériés."""
    if fin < debut:
        return 0
    n, d, un = 0, debut, dt.timedelta(days=1)
    while d <= fin:
        if est_ouvrable(d, feries):
            n += 1
        d += un
    return n


def fin_de_mois(annee: int, mois: int) -> dt.date:
    premier_suivant = dt.date(annee + (mois == 12), mois % 12 + 1, 1)
    return premier_suivant - dt.timedelta(days=1)
