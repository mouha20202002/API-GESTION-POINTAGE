"""Calculs de présence / absence (feuilles LISTE DES AGENTS, SITUATION DE L'AGENT, RECAP)."""
import datetime as dt

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from ..models import Affectation, Agent, Autorisation, Pointage, Service
from .calendrier import est_ouvrable, jours_ouvrables

UN_JOUR = dt.timedelta(days=1)


def jours_autorises(db: Session, matricule: str, service: str, d0: dt.date, d1: dt.date,
                    feries: set[dt.date]) -> int:
    """Jours ouvrables couverts par une autorisation non annulée dans [d0, d1].
    Le jour de reprise (date_retour) n'est pas compté, comme NETWORKDAYS(depart, retour-1)."""
    if d1 < d0:
        return 0
    q = select(Autorisation).where(
        Autorisation.matricule == matricule, Autorisation.service_code == service,
        Autorisation.annule.is_(False), Autorisation.date_depart <= d1, Autorisation.date_retour > d0)
    total = 0
    for a in db.scalars(q):
        total += jours_ouvrables(max(a.date_depart, d0), min(a.date_retour - UN_JOUR, d1), feries)
    return total


def stats_periode(db: Session, aff: Affectation, debut: dt.date, fin: dt.date, feries: set[dt.date]) -> dict:
    """Bornes réelles = période ∩ [prise de service, date d'affectation]."""
    d0 = max(debut, aff.date_prise_service)
    d1 = fin if aff.date_affectation is None else min(fin, aff.date_affectation)
    if d1 < d0:
        return dict(debut=d0, fin=d1, ouvrables=0, presents=0, absences=0, autorises=0,
                    non_justifies=0, anomalie=False)
    presents = db.scalar(select(func.count(Pointage.id)).where(
        Pointage.matricule == aff.matricule, Pointage.service_code == aff.service_code,
        Pointage.date >= d0, Pointage.date <= d1)) or 0
    ouvrables = jours_ouvrables(d0, d1, feries)
    autorises = jours_autorises(db, aff.matricule, aff.service_code, d0, d1, feries)
    brut = ouvrables - presents - autorises
    return dict(debut=d0, fin=d1, ouvrables=ouvrables, presents=presents,
                absences=max(ouvrables - presents, 0),   # définition de la LISTE DES AGENTS (col. I/J)
                autorises=autorises, non_justifies=max(brut, 0), anomalie=brut < 0)


def choisir_affectation(agent: Agent, service: str | None) -> Affectation | None:
    candidates = [a for a in agent.affectations if service is None or a.service_code == service]
    presentes = [a for a in candidates if a.etat == "PRESENT"]
    pool = presentes or candidates
    return pool[-1] if pool else None


def situation_agent(db: Session, agent: Agent, service: str | None, ref: dt.date,
                    feries: set[dt.date]) -> dict | None:
    aff = choisir_affectation(agent, service)
    if aff is None:
        return None
    s = stats_periode(db, aff, dt.date(ref.year, 1, 1), ref, feries)
    return dict(matricule=agent.matricule, prenom=agent.prenom, nom=agent.nom, service=aff.service_code,
                periode_debut=s["debut"], periode_fin=s["fin"], jours_ouvrables=s["ouvrables"],
                jours_presents=s["presents"], jours_absence_autorises=s["autorises"],
                jours_absence_non_justifies=s["non_justifies"], anomalie=s["anomalie"])


def _totaux(lignes: list[dict]) -> dict:
    t = {"HOMME": dict(effectif=0, presences=0, absences=0), "FEMME": dict(effectif=0, presences=0, absences=0)}
    for l in lignes:
        for k in ("effectif", "presences", "absences"):
            t[l["sexe"]][k] += l[k]
    return t


def recap_jour(db: Session, jour: dt.date, feries: set[dt.date]) -> dict:
    """RECAP : situation journalière par service et par sexe."""
    ouvrable = est_ouvrable(jour, feries)
    lignes = []
    for code in db.scalars(select(Service.code).order_by(Service.code)):
        for sexe in ("HOMME", "FEMME"):
            effectif = db.scalar(select(func.count(Affectation.id)).join(Agent).where(
                Affectation.service_code == code, Affectation.etat == "PRESENT",
                Affectation.date_prise_service <= jour, Agent.sexe == sexe)) or 0
            presences = db.scalar(select(func.count(Pointage.id)).join(Agent).where(
                Pointage.service_code == code, Pointage.date == jour, Agent.sexe == sexe)) or 0
            absences = max(effectif * int(ouvrable) - presences, 0)
            lignes.append(dict(service=code, sexe=sexe, effectif=effectif, presences=presences, absences=absences))
    return dict(periode_debut=jour, periode_fin=jour, est_jour_ouvrable=ouvrable,
                lignes=lignes, totaux=_totaux(lignes))


def recap_periode(db: Session, debut: dt.date, fin: dt.date, feries: set[dt.date]) -> dict:
    """RECAP : situation mensuelle ou annuelle (présences et absences cumulées par service/sexe)."""
    agg: dict[tuple[str, str], dict] = {}
    for code in db.scalars(select(Service.code).order_by(Service.code)):
        for sexe in ("HOMME", "FEMME"):
            agg[(code, sexe)] = dict(service=code, sexe=sexe, effectif=0, presences=0, absences=0)
    q = select(Affectation).options(joinedload(Affectation.agent))
    for aff in db.scalars(q):
        cle = (aff.service_code, aff.agent.sexe)
        if cle not in agg:
            continue
        if aff.etat == "PRESENT":
            agg[cle]["effectif"] += 1
        s = stats_periode(db, aff, debut, fin, feries)
        agg[cle]["presences"] += s["presents"]
        agg[cle]["absences"] += s["absences"]
    lignes = list(agg.values())
    return dict(periode_debut=debut, periode_fin=fin, est_jour_ouvrable=None,
                lignes=lignes, totaux=_totaux(lignes))


def liste_presence(db: Session, jour: dt.date, service: str) -> list[Agent]:
    q = (select(Agent).join(Pointage, Pointage.matricule == Agent.matricule)
         .where(Pointage.date == jour, Pointage.service_code == service).order_by(Agent.nom, Agent.prenom))
    return list(db.scalars(q))


def liste_absence(db: Session, jour: dt.date, service: str) -> list[tuple[Agent, bool]]:
    """Agents PRESENT du service sans pointage ce jour ; `justifie` si une autorisation couvre le jour."""
    presents = {m for (m,) in db.execute(select(Pointage.matricule).where(
        Pointage.date == jour, Pointage.service_code == service))}
    q = (select(Agent).join(Affectation, Affectation.matricule == Agent.matricule)
         .where(Affectation.service_code == service, Affectation.etat == "PRESENT",
                Affectation.date_prise_service <= jour).order_by(Agent.nom, Agent.prenom))
    resultat = []
    for agent in db.scalars(q):
        if agent.matricule in presents:
            continue
        couvert = db.scalar(select(func.count(Autorisation.id)).where(
            Autorisation.matricule == agent.matricule, Autorisation.service_code == service,
            Autorisation.annule.is_(False), Autorisation.date_depart <= jour,
            Autorisation.date_retour > jour)) or 0
        resultat.append((agent, couvert > 0))
    return resultat
