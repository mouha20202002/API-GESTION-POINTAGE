"""Règles métier extraites des formules du classeur (feuilles ENREGISTEMENT et CONGE ET PERMISSION)."""
import datetime as dt

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..models import Affectation, Agent, Service


def norm(valeur: str) -> str:
    return valeur.strip().upper()


def exiger_service(db: Session, code: str) -> str:
    code = norm(code)
    if db.get(Service, code) is None:
        raise HTTPException(422, f"Service inconnu : {code}")
    return code


def exiger_agent(db: Session, matricule: str) -> Agent:
    agent = db.get(Agent, norm(matricule))
    if agent is None:
        raise HTTPException(404, f"Agent introuvable : {norm(matricule)}")
    return agent


def affectation_valide(db: Session, matricule: str, service: str, jour: dt.date) -> Affectation | None:
    """Affectation de l'agent dans ce service couvrant `jour` (équivalent du contrôle 'CETTE PERSONNE EST AFFECTEE')."""
    lignes = db.scalars(select(Affectation).where(
        Affectation.matricule == matricule, Affectation.service_code == service))
    for a in lignes:
        if a.date_prise_service <= jour and (a.date_affectation is None or jour <= a.date_affectation):
            return a
    return None


def statut_arrivee(heure: dt.time | None) -> tuple[str | None, str | None]:
    """Colonne 'SITUATION DE L'AGENT' : retard si l'heure d'arrivée dépasse la marge matinale (ELEMENT!G3)."""
    if heure is None:
        return None, None
    if heure > settings.heure_limite_matin:
        return "EN_RETARD", "VOUS ETES EN RETARD"
    return "A_L_HEURE", "BIENVENUE"
