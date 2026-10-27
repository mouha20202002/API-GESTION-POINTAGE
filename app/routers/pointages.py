import datetime as dt

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from ..database import get_db
from ..models import Pointage
from ..schemas import PointageDepart, PointageIn, PointageOut
from ..services.calendrier import MOIS_FR, charger_feries
from ..services.regles import affectation_valide, exiger_agent, exiger_service, norm, statut_arrivee

router = APIRouter(prefix="/pointages", tags=["Pointages"])


def _out(p: Pointage) -> PointageOut:
    statut, message = statut_arrivee(p.heure_arrivee)
    a = p.agent
    return PointageOut(id=p.id, date=p.date, heure_arrivee=p.heure_arrivee, heure_depart=p.heure_depart,
                       matricule=a.matricule, prenom=a.prenom, nom=a.nom, sexe=a.sexe, fonction=a.fonction,
                       service=p.service_code, statut=statut, message=message,
                       mois=MOIS_FR[p.date.month - 1], annee=p.date.year)


@router.post("", response_model=PointageOut, status_code=201)
def enregistrer(p: PointageIn, db: Session = Depends(get_db)):
    """Enregistrement journalier. Reprend les contrôles de la colonne 'ERREUR D'ENREGISTEMENT'."""
    agent = exiger_agent(db, p.matricule)
    service = exiger_service(db, p.service_code)
    if p.date.weekday() >= 5:
        raise HTTPException(422, "ON EST EN WEEK END")
    if p.date in charger_feries(db):
        raise HTTPException(422, "JOUR FERIE")
    if affectation_valide(db, agent.matricule, service, p.date) is None:
        raise HTTPException(422, "CETTE PERSONNE N'EST PAS (OU PLUS) AFFECTEE A CE SERVICE A CETTE DATE")
    if p.heure_arrivee and p.heure_depart and p.heure_depart <= p.heure_arrivee:
        raise HTTPException(422, "heure_depart doit être postérieure à heure_arrivee")
    pt = Pointage(date=p.date, heure_arrivee=p.heure_arrivee, heure_depart=p.heure_depart,
                  matricule=agent.matricule, service_code=service)
    db.add(pt)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "VOUS ETES DÉJÀ ENREGISTRE POUR CE JOUR")
    pt.agent = agent
    return _out(pt)


@router.get("", response_model=list[PointageOut])
def lister(date: dt.date | None = None, date_debut: dt.date | None = None, date_fin: dt.date | None = None,
           service: str | None = None, matricule: str | None = None,
           limit: int = Query(200, le=1000), offset: int = 0, db: Session = Depends(get_db)):
    q = select(Pointage).options(joinedload(Pointage.agent)).order_by(Pointage.date.desc(), Pointage.heure_arrivee)
    if date:
        q = q.where(Pointage.date == date)
    if date_debut:
        q = q.where(Pointage.date >= date_debut)
    if date_fin:
        q = q.where(Pointage.date <= date_fin)
    if service:
        q = q.where(Pointage.service_code == norm(service))
    if matricule:
        q = q.where(Pointage.matricule == norm(matricule))
    return [_out(p) for p in db.scalars(q.limit(limit).offset(offset))]


@router.patch("/{pointage_id}/depart", response_model=PointageOut)
def enregistrer_depart(pointage_id: int, p: PointageDepart, db: Session = Depends(get_db)):
    pt = db.get(Pointage, pointage_id)
    if pt is None:
        raise HTTPException(404, "Pointage introuvable")
    if pt.heure_arrivee and p.heure_depart <= pt.heure_arrivee:
        raise HTTPException(422, "heure_depart doit être postérieure à heure_arrivee")
    pt.heure_depart = p.heure_depart
    db.commit()
    return _out(pt)


@router.delete("/{pointage_id}", status_code=204)
def supprimer(pointage_id: int, db: Session = Depends(get_db)):
    pt = db.get(Pointage, pointage_id)
    if pt is None:
        raise HTTPException(404, "Pointage introuvable")
    db.delete(pt)
    db.commit()
