"""Modèle de données dérivé des tableaux du classeur GESTION_DES_POINTAGE.xlsx

Tableau1 (LISTE DES AGENTS)      -> Agent + Affectation (un agent peut avoir plusieurs lignes/services)
Tableau2 (ENREGISTEMENT)         -> Pointage
Tableau3 (LISTE DE JOUR FERIER)  -> JourFerie
Tableau4 (CONGE ET PERMISSION)   -> Autorisation
ELEMENT (feuille cachée, listes) -> Service + constantes (enums dans schemas.py)
"""
import datetime as dt

from sqlalchemy import Boolean, Date, ForeignKey, Index, String, Time, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class Service(Base):
    __tablename__ = "services"
    code: Mapped[str] = mapped_column(String(20), primary_key=True)


class Agent(Base):
    __tablename__ = "agents"
    matricule: Mapped[str] = mapped_column(String(30), primary_key=True)
    prenom: Mapped[str] = mapped_column(String(100))
    nom: Mapped[str] = mapped_column(String(100))
    sexe: Mapped[str] = mapped_column(String(10))
    fonction: Mapped[str | None] = mapped_column(String(100), nullable=True)

    affectations: Mapped[list["Affectation"]] = relationship(
        back_populates="agent", cascade="all, delete-orphan", order_by="Affectation.date_prise_service"
    )


class Affectation(Base):
    """Une ligne de la LISTE DES AGENTS : agent x service, état PRESENT ou AFFECTE."""
    __tablename__ = "affectations"
    __table_args__ = (UniqueConstraint("matricule", "service_code", "date_prise_service"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    matricule: Mapped[str] = mapped_column(ForeignKey("agents.matricule"), index=True)
    service_code: Mapped[str] = mapped_column(ForeignKey("services.code"))
    etat: Mapped[str] = mapped_column(String(10), default="PRESENT")
    date_prise_service: Mapped[dt.date] = mapped_column(Date)
    date_affectation: Mapped[dt.date | None] = mapped_column(Date, nullable=True)  # date de départ du service

    agent: Mapped[Agent] = relationship(back_populates="affectations")


class Pointage(Base):
    __tablename__ = "pointages"
    __table_args__ = (
        UniqueConstraint("date", "matricule", "service_code"),  # règle "VOUS ETES DÉJÀ ENREGISTRE"
        Index("ix_pointages_date_service", "date", "service_code"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    date: Mapped[dt.date] = mapped_column(Date)
    heure_arrivee: Mapped[dt.time | None] = mapped_column(Time, nullable=True)
    heure_depart: Mapped[dt.time | None] = mapped_column(Time, nullable=True)
    matricule: Mapped[str] = mapped_column(ForeignKey("agents.matricule"), index=True)
    service_code: Mapped[str] = mapped_column(ForeignKey("services.code"))

    agent: Mapped[Agent] = relationship()


class Autorisation(Base):
    """Congé, permission, maladie, mission... (Tableau4)."""
    __tablename__ = "autorisations"

    id: Mapped[int] = mapped_column(primary_key=True)
    matricule: Mapped[str] = mapped_column(ForeignKey("agents.matricule"), index=True)
    service_code: Mapped[str] = mapped_column(ForeignKey("services.code"))
    date_depart: Mapped[dt.date] = mapped_column(Date)
    date_retour: Mapped[dt.date] = mapped_column(Date)  # jour de reprise : non compté comme absent
    motif: Mapped[str] = mapped_column(String(40))
    annule: Mapped[bool] = mapped_column(Boolean, default=False)

    agent: Mapped[Agent] = relationship()


class JourFerie(Base):
    __tablename__ = "jours_feries"
    date: Mapped[dt.date] = mapped_column(Date, primary_key=True)
    nom: Mapped[str] = mapped_column(String(120))
