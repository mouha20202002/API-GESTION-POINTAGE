import datetime as dt
import enum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Sexe(str, enum.Enum):
    HOMME = "HOMME"
    FEMME = "FEMME"


class Etat(str, enum.Enum):
    PRESENT = "PRESENT"
    AFFECTE = "AFFECTE"   # "AFFECTE(E )" dans le classeur : l'agent a quitté le service


class Motif(str, enum.Enum):  # liste ELEMENT!B2:B8
    CONGE = "CONGE"
    PERMISSION = "PERMISSION D'ABSENCE"
    MALADE = "MALADE"
    MISSION = "MISSION"
    ATELIER = "ATELIER"
    SEMINAIRE = "SEMINAIRE"
    AUTRE = "AUTRE"


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------- Agents ----------
class AffectationIn(BaseModel):
    service_code: str
    etat: Etat = Etat.PRESENT
    date_prise_service: dt.date
    date_affectation: dt.date | None = None

    @model_validator(mode="after")
    def _coherence(self):
        if self.etat == Etat.AFFECTE and self.date_affectation is None:
            raise ValueError("date_affectation obligatoire quand l'état est AFFECTE")
        if self.date_affectation and self.date_affectation < self.date_prise_service:
            raise ValueError("date_affectation antérieure à la date de prise de service")
        return self


class AffectationUpdate(BaseModel):
    etat: Etat | None = None
    date_affectation: dt.date | None = None


class AffectationOut(ORM):
    id: int
    service_code: str
    etat: str
    date_prise_service: dt.date
    date_affectation: dt.date | None


class AgentIn(BaseModel):
    matricule: str = Field(min_length=1, max_length=30)
    prenom: str = Field(min_length=1)
    nom: str = Field(min_length=1)
    sexe: Sexe
    fonction: str | None = None
    affectation: AffectationIn | None = None


class AgentUpdate(BaseModel):
    prenom: str | None = None
    nom: str | None = None
    sexe: Sexe | None = None
    fonction: str | None = None


class AgentOut(ORM):
    matricule: str
    prenom: str
    nom: str
    sexe: str
    fonction: str | None
    affectations: list[AffectationOut] = []


# ---------- Pointages ----------
class PointageIn(BaseModel):
    date: dt.date
    heure_arrivee: dt.time | None = None
    heure_depart: dt.time | None = None
    matricule: str
    service_code: str


class PointageDepart(BaseModel):
    heure_depart: dt.time


class PointageOut(BaseModel):
    id: int
    date: dt.date
    heure_arrivee: dt.time | None
    heure_depart: dt.time | None
    matricule: str
    prenom: str
    nom: str
    sexe: str
    fonction: str | None
    service: str
    statut: str | None          # A_L_HEURE | EN_RETARD
    message: str | None         # BIENVENUE | VOUS ETES EN RETARD
    mois: str
    annee: int


# ---------- Autorisations d'absence ----------
class AutorisationIn(BaseModel):
    matricule: str
    service_code: str
    date_depart: dt.date
    date_retour: dt.date
    motif: Motif

    @model_validator(mode="after")
    def _dates(self):
        if self.date_retour <= self.date_depart:
            raise ValueError("date_retour doit être postérieure à date_depart")
        return self


class AutorisationUpdate(BaseModel):
    date_depart: dt.date | None = None
    date_retour: dt.date | None = None
    motif: Motif | None = None


class AutorisationOut(BaseModel):
    id: int
    matricule: str
    prenom: str
    nom: str
    sexe: str
    fonction: str | None
    service: str
    date_depart: dt.date
    date_retour: dt.date
    motif: str
    annule: bool
    jours_autorises_annee: int
    notice: str                 # OK | N'EST PLUS DANS LE SERVICE | ERREUR DE PRISE DE SERVICE


# ---------- Jours fériés ----------
class JourFerieIn(BaseModel):
    date: dt.date
    nom: str


class JourFerieOut(ORM):
    date: dt.date
    nom: str


# ---------- Rapports ----------
class SituationAgent(BaseModel):
    matricule: str
    prenom: str
    nom: str
    service: str
    periode_debut: dt.date
    periode_fin: dt.date
    jours_ouvrables: int
    jours_presents: int
    jours_absence_autorises: int
    jours_absence_non_justifies: int
    anomalie: bool              # présences + absences autorisées > jours ouvrables (données à corriger)


class RecapLigne(BaseModel):
    service: str
    sexe: str
    effectif: int
    presences: int
    absences: int


class Recap(BaseModel):
    periode_debut: dt.date
    periode_fin: dt.date
    est_jour_ouvrable: bool | None = None
    lignes: list[RecapLigne]
    totaux: dict[str, dict[str, int]]   # {"HOMME": {"effectif":..,"presences":..,"absences":..}, "FEMME": {...}}


class AgentListe(BaseModel):
    matricule: str
    prenom: str
    nom: str
    sexe: str
    fonction: str | None
    justifie: bool | None = None        # absences : couvert par une autorisation ce jour-là


class ListeService(BaseModel):
    date: dt.date
    service: str
    note: str | None = None             # "ON EST EN WEEK END", "FERIER"
    total: int
    agents: list[AgentListe]
