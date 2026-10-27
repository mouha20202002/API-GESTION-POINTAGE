import datetime as dt

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, joinedload

from ..database import get_db
from ..models import Affectation, Agent
from ..schemas import (AffectationIn, AffectationOut, AffectationUpdate, AgentIn, AgentOut,
                       AgentUpdate, SituationAgent)
from ..services import stats
from ..services.calendrier import charger_feries
from ..services.regles import exiger_agent, exiger_service, norm

router = APIRouter(tags=["Agents"])


def _nouvelle_affectation(db: Session, matricule: str, p: AffectationIn) -> Affectation:
    return Affectation(matricule=matricule, service_code=exiger_service(db, p.service_code), etat=p.etat.value,
                       date_prise_service=p.date_prise_service, date_affectation=p.date_affectation)


@router.post("/agents", response_model=AgentOut, status_code=201)
def creer_agent(p: AgentIn, db: Session = Depends(get_db)):
    matricule = norm(p.matricule)
    if db.get(Agent, matricule):
        raise HTTPException(409, "Matricule déjà existant")
    agent = Agent(matricule=matricule, prenom=p.prenom.strip(), nom=p.nom.strip(),
                  sexe=p.sexe.value, fonction=p.fonction)
    if p.affectation:
        agent.affectations.append(_nouvelle_affectation(db, matricule, p.affectation))
    db.add(agent)
    db.commit()
    return agent


@router.get("/agents", response_model=list[AgentOut])
def lister_agents(service: str | None = None, etat: str | None = None, q: str | None = None,
                  limit: int = Query(200, le=1000), offset: int = 0, db: Session = Depends(get_db)):
    req = select(Agent).options(joinedload(Agent.affectations)).order_by(Agent.nom, Agent.prenom)
    if service or etat:
        req = req.join(Affectation)
        if service:
            req = req.where(Affectation.service_code == norm(service))
        if etat:
            req = req.where(Affectation.etat == etat.strip().upper())
    if q:
        like = f"%{q.strip()}%"
        req = req.where(or_(Agent.nom.ilike(like), Agent.prenom.ilike(like), Agent.matricule.ilike(like)))
    return db.scalars(req.limit(limit).offset(offset)).unique().all()


@router.get("/agents/{matricule}", response_model=AgentOut)
def lire_agent(matricule: str, db: Session = Depends(get_db)):
    return exiger_agent(db, matricule)


@router.patch("/agents/{matricule}", response_model=AgentOut)
def modifier_agent(matricule: str, p: AgentUpdate, db: Session = Depends(get_db)):
    agent = exiger_agent(db, matricule)
    for champ, valeur in p.model_dump(exclude_unset=True).items():
        setattr(agent, champ, valeur.value if hasattr(valeur, "value") else valeur)
    db.commit()
    return agent


@router.post("/agents/{matricule}/affectations", response_model=AffectationOut, status_code=201)
def ajouter_affectation(matricule: str, p: AffectationIn, db: Session = Depends(get_db)):
    agent = exiger_agent(db, matricule)
    aff = _nouvelle_affectation(db, agent.matricule, p)
    db.add(aff)
    db.commit()
    return aff


@router.patch("/affectations/{aff_id}", response_model=AffectationOut)
def modifier_affectation(aff_id: int, p: AffectationUpdate, db: Session = Depends(get_db)):
    """Marquer un agent comme AFFECTE (parti du service) en renseignant la date d'affectation."""
    aff = db.get(Affectation, aff_id)
    if aff is None:
        raise HTTPException(404, "Affectation introuvable")
    if p.etat is not None:
        aff.etat = p.etat.value
    if p.date_affectation is not None:
        aff.date_affectation = p.date_affectation
    if aff.etat == "AFFECTE" and aff.date_affectation is None:
        raise HTTPException(422, "date_affectation obligatoire pour l'état AFFECTE")
    if aff.date_affectation and aff.date_affectation < aff.date_prise_service:
        raise HTTPException(422, "date_affectation antérieure à la prise de service")
    db.commit()
    return aff


@router.get("/agents/{matricule}/situation", response_model=SituationAgent)
def situation(matricule: str, service: str | None = None, date_reference: dt.date | None = None,
              db: Session = Depends(get_db)):
    """Feuille 'SITUATION DE L'AGENT EN SERVICE' : présences, absences autorisées et non justifiées depuis le 1er janvier."""
    agent = exiger_agent(db, matricule)
    ref = date_reference or dt.date.today()
    res = stats.situation_agent(db, agent, norm(service) if service else None, ref, charger_feries(db))
    if res is None:
        raise HTTPException(404, "Aucune affectation pour cet agent / service")
    return res
