from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI

from .database import Base, SessionLocal, engine
from .models import Service
from .routers import agents, autorisations, jours_feries, pointages, rapports, referentiels
from .security import verifier_cle

SERVICES_PAR_DEFAUT = ["SAI", "DPS", "DPJ", "DEP", "DAGI", "DMRHF", "SSP"]  # ELEMENT!A2:A8


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        if db.query(Service).count() == 0:
            db.add_all(Service(code=c) for c in SERVICES_PAR_DEFAUT)
            db.commit()
    yield


app = FastAPI(title="API de gestion des pointages", version="1.0.0", lifespan=lifespan,
              dependencies=[Depends(verifier_cle)])

for module in (referentiels, agents, pointages, autorisations, jours_feries, rapports):
    app.include_router(module.router)


@app.get("/", tags=["Santé"])
def racine():
    return {"service": "API de gestion des pointages", "docs": "/docs"}
