from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..models import Service
from ..schemas import Etat, Motif, Sexe
from ..services.regles import norm

router = APIRouter(tags=["Référentiels"])


class ServiceIn(BaseModel):
    code: str


@router.get("/referentiels")
def referentiels(db: Session = Depends(get_db)):
    """Listes de la feuille cachée ELEMENT (services, motifs d'autorisation, états, sexes, horaires)."""
    return {
        "services": list(db.scalars(select(Service.code).order_by(Service.code))),
        "motifs": [m.value for m in Motif],
        "etats": [e.value for e in Etat],
        "sexes": [s.value for s in Sexe],
        "horaires": {
            "heure_normale_matin": settings.heure_normale_matin,
            "heure_limite_matin": settings.heure_limite_matin,
            "heure_normale_soir": settings.heure_normale_soir,
            "heure_limite_soir": settings.heure_limite_soir,
        },
    }


@router.post("/services", status_code=201)
def creer_service(p: ServiceIn, db: Session = Depends(get_db)):
    code = norm(p.code)
    if db.get(Service, code):
        raise HTTPException(409, "Service déjà existant")
    db.add(Service(code=code))
    db.commit()
    return {"code": code}
