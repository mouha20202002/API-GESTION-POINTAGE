# API de gestion des pointages

API REST (FastAPI + SQLAlchemy) dérivée du classeur `GESTION_DES_POINTAGE.xlsx`.

## Démarrage

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env                       # définir POINTAGE_API_KEY
python scripts/import_excel.py GESTION_DES_POINTAGE.xlsx --reset   # optionnel : reprise des données
uvicorn app.main:app --reload              # documentation interactive : http://127.0.0.1:8000/docs
```

Le classeur est chiffré : fournir son mot de passe avec `--password`, la variable
`POINTAGE_XLSX_PASSWORD`, ou en saisie masquée (rien n'est écrit en dur dans le code).

Tests : `pip install -r requirements-dev.txt && pytest`
Parité avec Excel : `python scripts/verifier_excel.py GESTION_DES_POINTAGE.xlsx`

## Correspondance classeur -> API

| Feuille Excel | Ressource API |
|---|---|
| ELEMENT (cachée : listes, horaires) | `GET /referentiels`, `POST /services`, réglages `.env` |
| LISTE DES AGENTS | `/agents`, `/agents/{matricule}/affectations`, `/affectations/{id}` |
| ENREGISTEMENT | `/pointages` (POST arrivée, PATCH `/{id}/depart`, GET filtres) |
| CONGE ET PERMISSION | `/autorisations` (+ `/{id}/annuler`) |
| LISTE DE JOUR FERIER | `/jours-feries` (+ `POST /generer/{annee}` pour les fêtes fixes) |
| LISTE DE PRESENCE / D'ABSENCE PAR SERVICE | `GET /rapports/presences`, `GET /rapports/absences` |
| RECAP | `GET /rapports/jour`, `/rapports/mensuel`, `/rapports/annuel` |
| SITUATION DE L'AGENT EN SERVICE | `GET /agents/{matricule}/situation` |

## Règles reprises des formules Excel

- Retard : arrivée strictement après `heure_limite_matin` (08:30, cellule ELEMENT!G3).
- Pointage refusé : week-end, jour férié, agent non affecté au service à cette date (422) ; doublon agent/jour/service (409).
- Jours ouvrables = lundi-vendredi hors jours fériés, bornes incluses (équivalent de `NETWORKDAYS`).
- Autorisation : le jour de reprise (`date_retour`) n'est pas compté ; les autorisations annulées sont ignorées.
- Absences non justifiées = jours ouvrables - présences - jours autorisés (`anomalie=true` si négatif).
- Un agent peut avoir plusieurs affectations (PRESENT dans un service, AFFECTE dans un autre).

## Limites connues

- Pas de gestion d'utilisateurs/rôles : une clé d'API unique (`X-API-Key`). À renforcer avant une mise en production.
- La périodicité JOUR/NUIT de la feuille ELEMENT n'est pas reprise.
- Les fêtes mobiles (Tabaski, Magal, Gamou, Korité...) se saisissent chaque année via `POST /jours-feries`.
- SQLite par défaut ; PostgreSQL via `POINTAGE_DATABASE_URL` (ajouter le pilote, ex. `psycopg`).
