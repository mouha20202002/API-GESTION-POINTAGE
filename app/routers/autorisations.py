import datetime as dt

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from ..database import get_db
from ..models import Affectation, Autorisation
from ..schemas import AutorisationIn, AutorisationOut, AutorisationUpdate
from ..services.calendrier import charger_feries, jours_ouvrables
from ..services.regles import exiger_agent, exiger_service, norm

router = APIRouter(prefix="/autorisations", tags=["Congés et permissions"])


def _notice(db: Session, a: Autorisation) -> str:
    """Colonne 'NOTICE ERREUR DE DATE DE SERVICE' du classeur."""
    courante = db.scalar(select(Affectation).where(
        Affectation.matricule == a.matricule, Affectation.etat == "PRESENT").order_by(
        Affectation.date_prise_service.desc()))
    if courante is None or courante.service_code != a.service_code:
        return "N'EST PLUS DANS LE SERVICE"
    if courante.date_prise_service <= a.date_depart and courante.date_prise_service < a.date_retour:
        return "OK"
    return "ERREUR DE PRISE DE SERVICE"


def _out(db: Session, a: Autorisation, ref: dt.date, feries: set[dt.date]) -> AutorisationOut:
    """Jours ouvrables de CETTE autorisation tombant entre le 1er janvier et `ref` (colonne ANNEE D'ABSENCE AUTORISE)."""
    jours = 0
    if not a.annule:
        d0 = max(a.date_depart, dt.date(ref.year, 1, 1))
        d1 = min(a.date_retour - dt.timedelta(days=1), ref)
        jours = jours_ouvrables(d0, d1, feries)
    ag = a.agent
    return AutorisationOut(id=a.id, matricule=a.matricule, prenom=ag.prenom, nom=ag.nom, sexe=ag.sexe,
                           fonction=ag.fonction, service=a.service_code, date_depart=a.date_depart,
                           date_retour=a.date_retour, motif=a.motif, annule=a.annule,
                           jours_autorises_annee=jours, notice=_notice(db, a))


@router.post("", response_model=AutorisationOut, status_code=201)
def creer(p: AutorisationIn, db: Session = Depends(get_db)):
    agent = exiger_agent(db, p.matricule)
    a = Autorisation(matricule=agent.matricule, service_code=exiger_service(db, p.service_code),
                     date_depart=p.date_depart, date_retour=p.date_retour, motif=p.motif.value)
    db.add(a)
    db.commit()
    a.agent = agent
    return _out(db, a, dt.date.today(), charger_feries(db))


@router.get("", response_model=list[AutorisationOut])
def lister(matricule: str | None = None, service: str | None = None, annee: int | None = None,
           inclure_annulees: bool = False, limit: int = Query(200, le=1000), offset: int = 0,
           db: Session = Depends(get_db)):
    q = select(Autorisation).options(joinedload(Autorisation.agent)).order_by(Autorisation.date_depart.desc())
    if matricule:
        q = q.where(Autorisation.matricule == norm(matricule))
    if service:
        q = q.where(Autorisation.service_code == norm(service))
    if annee:
        q = q.where(Autorisation.date_depart <= dt.date(annee, 12, 31), Autorisation.date_retour >= dt.date(annee, 1, 1))
    if not inclure_annulees:
        q = q.where(Autorisation.annule.is_(False))
    feries, today = charger_feries(db), dt.date.today()
    return [_out(db, a, today, feries) for a in db.scalars(q.limit(limit).offset(offset))]


@router.get("/{aut_id}", response_model=AutorisationOut)
def lire(aut_id: int, db: Session = Depends(get_db)):
    a = db.get(Autorisation, aut_id)
    if a is None:
        raise HTTPException(404, "Autorisation introuvable")
    return _out(db, a, dt.date.today(), charger_feries(db))


@router.patch("/{aut_id}", response_model=AutorisationOut)
def modifier(aut_id: int, p: AutorisationUpdate, db: Session = Depends(get_db)):
    a = db.get(Autorisation, aut_id)
    if a is None:
        raise HTTPException(404, "Autorisation introuvable")
    if p.date_depart:
        a.date_depart = p.date_depart
    if p.date_retour:
        a.date_retour = p.date_retour
    if p.motif:
        a.motif = p.motif.value
    if a.date_retour <= a.date_depart:
        raise HTTPException(422, "date_retour doit être postérieure à date_depart")
    db.commit()
    return _out(db, a, dt.date.today(), charger_feries(db))


@router.post("/{aut_id}/annuler", response_model=AutorisationOut)
def annuler(aut_id: int, db: Session = Depends(get_db)):
    """Colonne ANNULATION du classeur."""
    a = db.get(Autorisation, aut_id)
    if a is None:
        raise HTTPException(404, "Autorisation introuvable")
    a.annule = True
    db.commit()
    return _out(db, a, dt.date.today(), charger_feries(db))
