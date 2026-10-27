import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.database import Base, get_db
from app.main import app
from app.models import Service

LUNDI, MARDI, MERCREDI, JEUDI, VENDREDI, SAMEDI = (
    "2026-03-02", "2026-03-03", "2026-03-04", "2026-03-05", "2026-03-06", "2026-03-07")


@pytest.fixture()
def client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with Session() as db:
        db.add_all([Service(code="SSP"), Service(code="DAGI")])
        db.commit()

    def _db():
        with Session() as db:
            yield db

    app.dependency_overrides[get_db] = _db
    c = TestClient(app)
    c.post("/agents", json={"matricule": "760947k", "prenom": "Bassirou", "nom": "Sarre", "sexe": "HOMME",
                            "fonction": "STATISTICIEN",
                            "affectation": {"service_code": "ssp", "date_prise_service": LUNDI}})
    yield c
    app.dependency_overrides.clear()


def pointer(c, jour, heure="08:00:00", mat="760947K", svc="SSP"):
    return c.post("/pointages", json={"date": jour, "heure_arrivee": heure, "matricule": mat, "service_code": svc})


def test_matricule_et_service_normalises(client):
    r = client.get("/agents/760947K")
    assert r.status_code == 200 and r.json()["affectations"][0]["service_code"] == "SSP"


def test_retard_apres_la_marge_matinale(client):
    assert pointer(client, LUNDI, "08:30:00").json()["message"] == "BIENVENUE"
    r = pointer(client, MARDI, "08:31:00").json()
    assert r["statut"] == "EN_RETARD" and r["message"] == "VOUS ETES EN RETARD" and r["mois"] == "mars"


def test_week_end_et_jour_ferie_refuses(client):
    assert pointer(client, SAMEDI).status_code == 422
    client.post("/jours-feries", json={"date": MERCREDI, "nom": "Test"})
    r = pointer(client, MERCREDI)
    assert r.status_code == 422 and "FERIE" in r.json()["detail"]


def test_doublon_refuse(client):
    assert pointer(client, LUNDI).status_code == 201
    assert pointer(client, LUNDI).status_code == 409


def test_agent_affecte_ne_peut_plus_pointer(client):
    aff_id = client.get("/agents/760947K").json()["affectations"][0]["id"]
    client.patch(f"/affectations/{aff_id}", json={"etat": "AFFECTE", "date_affectation": MARDI})
    assert pointer(client, MARDI).status_code == 201     # dernier jour dans le service
    assert pointer(client, MERCREDI).status_code == 422


def test_service_sans_affectation_refuse(client):
    assert pointer(client, LUNDI, svc="DAGI").status_code == 422


def test_situation_agent_absence_non_justifiee(client):
    pointer(client, LUNDI), pointer(client, MARDI)
    # permission du mercredi au vendredi : le jour de reprise (vendredi) n'est pas compté -> 2 jours
    r = client.post("/autorisations", json={"matricule": "760947K", "service_code": "SSP", "motif": "MISSION",
                                            "date_depart": MERCREDI, "date_retour": VENDREDI})
    assert r.status_code == 201 and r.json()["notice"] == "OK"
    s = client.get("/agents/760947K/situation", params={"date_reference": VENDREDI}).json()
    assert (s["jours_ouvrables"], s["jours_presents"], s["jours_absence_autorises"],
            s["jours_absence_non_justifies"]) == (5, 2, 2, 1)


def test_jour_ferie_exclu_du_decompte_des_conges(client):
    client.post("/jours-feries", json={"date": MERCREDI, "nom": "Test"})
    r = client.post("/autorisations", json={"matricule": "760947K", "service_code": "SSP", "motif": "CONGE",
                                            "date_depart": MARDI, "date_retour": VENDREDI})
    s = client.get("/agents/760947K/situation", params={"date_reference": VENDREDI}).json()
    assert s["jours_absence_autorises"] == 2          # mardi + jeudi (mercredi férié)


def test_annulation_retire_les_jours_autorises(client):
    aut = client.post("/autorisations", json={"matricule": "760947K", "service_code": "SSP", "motif": "CONGE",
                                              "date_depart": MARDI, "date_retour": VENDREDI}).json()
    client.post(f"/autorisations/{aut['id']}/annuler")
    s = client.get("/agents/760947K/situation", params={"date_reference": VENDREDI}).json()
    assert s["jours_absence_autorises"] == 0


def test_liste_absences_signale_les_absences_justifiees(client):
    client.post("/autorisations", json={"matricule": "760947K", "service_code": "SSP", "motif": "MALADE",
                                        "date_depart": LUNDI, "date_retour": MERCREDI})
    r = client.get("/rapports/absences", params={"date": MARDI, "service": "SSP"}).json()
    assert r["total"] == 1 and r["agents"][0]["justifie"] is True
    assert client.get("/rapports/absences", params={"date": SAMEDI, "service": "SSP"}).json()["note"] == "ON EST EN WEEK END"


def test_recap_jour(client):
    pointer(client, LUNDI)
    r = client.get("/rapports/jour", params={"date": LUNDI}).json()
    ssp_h = next(l for l in r["lignes"] if l["service"] == "SSP" and l["sexe"] == "HOMME")
    assert (ssp_h["effectif"], ssp_h["presences"], ssp_h["absences"]) == (1, 1, 0)


def test_cle_api(client, monkeypatch):
    monkeypatch.setattr(settings, "api_key", "secret")
    assert client.get("/referentiels").status_code == 401
    assert client.get("/referentiels", headers={"X-API-Key": "secret"}).status_code == 200
