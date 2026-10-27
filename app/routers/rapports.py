import datetime as dt

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..schemas import AgentListe, ListeService, Recap
from ..services import stats
from ..services.calendrier import charger_feries, est_ouvrable, fin_de_mois
from ..services.regles import exiger_service

router = APIRouter(prefix="/rapports", tags=["Rapports (feuille RECAP)"])


@router.get("/jour", response_model=Recap)
def recap_jour(date: dt.date | None = None, db: Session = Depends(get_db)):
    """Situation journalière des services : effectifs, présences, absences par sexe."""
    return stats.recap_jour(db, date or dt.date.today(), charger_feries(db))


@router.get("/mensuel", response_model=Recap)
def recap_mensuel(annee: int = Query(ge=2000, le=2100), mois: int = Query(ge=1, le=12),
                  date_reference: dt.date | None = None, db: Session = Depends(get_db)):
    debut, fin = dt.date(annee, mois, 1), fin_de_mois(annee, mois)
    return stats.recap_periode(db, debut, min(fin, date_reference or dt.date.today()), charger_feries(db))


@router.get("/annuel", response_model=Recap)
def recap_annuel(annee: int = Query(ge=2000, le=2100), date_reference: dt.date | None = None,
                 db: Session = Depends(get_db)):
    return stats.recap_periode(db, dt.date(annee, 1, 1),
                               min(dt.date(annee, 12, 31), date_reference or dt.date.today()), charger_feries(db))


def _note(jour: dt.date, feries: set[dt.date]) -> str | None:
    we, fe = jour.weekday() >= 5, jour in feries
    return "FERIER ET WEEK END" if we and fe else "FERIER" if fe else "ON EST EN WEEK END" if we else None


@router.get("/presences", response_model=ListeService)
def liste_presences(date: dt.date, service: str, db: Session = Depends(get_db)):
    """Feuille 'LISTE DE PRESENCE PAR SERVICE'."""
    service, feries = exiger_service(db, service), charger_feries(db)
    note = _note(date, feries)
    agents = [] if note else stats.liste_presence(db, date, service)
    return ListeService(date=date, service=service, note=note, total=len(agents),
                        agents=[AgentListe.model_validate(a, from_attributes=True) for a in agents])


@router.get("/absences", response_model=ListeService)
def liste_absences(date: dt.date, service: str, db: Session = Depends(get_db)):
    """Feuille 'LISTE D'ABSENCE PAR SERVICE' (+ indicateur `justifie` si une autorisation couvre le jour)."""
    service, feries = exiger_service(db, service), charger_feries(db)
    note = _note(date, feries)
    lignes = [] if note else stats.liste_absence(db, date, service)
    agents = [AgentListe(matricule=a.matricule, prenom=a.prenom, nom=a.nom, sexe=a.sexe,
                         fonction=a.fonction, justifie=j) for a, j in lignes]
    return ListeService(date=date, service=service, note=note, total=len(agents), agents=agents)
