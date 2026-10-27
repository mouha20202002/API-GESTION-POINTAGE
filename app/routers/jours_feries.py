import datetime as dt

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import extract, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import JourFerie
from ..schemas import JourFerieIn, JourFerieOut

router = APIRouter(prefix="/jours-feries", tags=["Jours fériés"])

# Fêtes à date fixe (les 6 premières lignes de la feuille LISTE DE JOUR FERIER)
FIXES = [(1, 1, "Jour de l'An"), (4, 4, "Fête Nationale du Sénégal (Indépendance)"), (5, 1, "Fête du Travail"),
         (8, 15, "Assomption"), (11, 1, "Toussaint"), (12, 25, "Noël")]


@router.get("", response_model=list[JourFerieOut])
def lister(annee: int | None = None, db: Session = Depends(get_db)):
    q = select(JourFerie).order_by(JourFerie.date)
    if annee:
        q = q.where(extract("year", JourFerie.date) == annee)
    return db.scalars(q).all()


@router.post("", response_model=JourFerieOut, status_code=201)
def ajouter(p: JourFerieIn, db: Session = Depends(get_db)):
    """Pour les fêtes mobiles (Tabaski, Magal, Gamou, Korité...) : à saisir chaque année."""
    if db.get(JourFerie, p.date):
        raise HTTPException(409, "Date déjà enregistrée")
    jf = JourFerie(date=p.date, nom=p.nom.strip())
    db.add(jf)
    db.commit()
    return jf


@router.post("/generer/{annee}", response_model=list[JourFerieOut], status_code=201)
def generer_fixes(annee: int, db: Session = Depends(get_db)):
    """Génère les fêtes à date fixe de l'année (équivalent des formules NUMBERVALUE du classeur)."""
    crees = []
    for mois, jour, nom in FIXES:
        d = dt.date(annee, mois, jour)
        if db.get(JourFerie, d) is None:
            jf = JourFerie(date=d, nom=nom)
            db.add(jf)
            crees.append(jf)
    db.commit()
    return crees


@router.delete("/{date}", status_code=204)
def supprimer(date: dt.date, db: Session = Depends(get_db)):
    jf = db.get(JourFerie, date)
    if jf is None:
        raise HTTPException(404, "Jour férié introuvable")
    db.delete(jf)
    db.commit()
