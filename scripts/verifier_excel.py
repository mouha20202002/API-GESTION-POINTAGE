"""Compare les calculs de l'API aux valeurs en cache du classeur (LISTE DES AGENTS, CONGE ET PERMISSION).

    POINTAGE_DATABASE_URL=sqlite:///./pointage.db python scripts/verifier_excel.py GESTION_DES_POINTAGE.xlsx
"""
import argparse
import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from import_excel import lire_tableau, ouvrir_classeur, _date, _txt  # noqa: E402
from sqlalchemy import select  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models import Affectation, Autorisation  # noqa: E402
from app.services.calendrier import charger_feries, jours_ouvrables  # noqa: E402
from app.services.stats import jours_autorises, stats_periode  # noqa: E402


def _num(v):
    return v if isinstance(v, (int, float)) else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("classeur")
    ap.add_argument("--password")
    a = ap.parse_args()
    wb = ouvrir_classeur(a.classeur, a.password)
    ref = _date(wb["RECAP"]["D5"].value)           # TODAY() mis en cache à la dernière sauvegarde
    debut_mois, debut_an = dt.date(ref.year, ref.month, 1), dt.date(ref.year, 1, 1)
    print(f"Date de référence du classeur : {ref}\n")

    ecarts = 0
    with SessionLocal() as db:
        feries = charger_feries(db)

        print("== LISTE DES AGENTS : absence/présence du mois et de l'année ==")
        for l in lire_tableau(wb, "Tableau1"):
            mat, svc, prise = _txt(l["N° MATRICULE"]), _txt(l["SERVICE"]), _date(l["DATE DE PRISE DE SERVICE"])
            if not mat:
                continue
            aff = db.scalar(select(Affectation).where(Affectation.matricule == mat.upper(),
                            Affectation.service_code == svc.upper(), Affectation.date_prise_service == prise))
            mois, an = stats_periode(db, aff, debut_mois, ref, feries), stats_periode(db, aff, debut_an, ref, feries)
            attendu = dict(abs_mois=_num(l["ABSENCE MOIS"]), abs_an=_num(l["ABSENCE ANNUELLE"]),
                           pres_mois=_num(l["PRESENCE DU MOIS"]), pres_an=_num(l["PRESENCE ANNUELLE"]))
            obtenu = dict(abs_mois=mois["absences"], abs_an=an["absences"],
                          pres_mois=mois["presents"], pres_an=an["presents"])
            for k, v in attendu.items():
                if v is None:      # cellule vide dans Excel (ex. agent affecté) : non comparable
                    continue
                ok = v == obtenu[k]
                ecarts += not ok
                print(f"  {mat:9} {svc:6} {aff.etat:8} {k:9} excel={v:<5} api={obtenu[k]:<5} {'OK' if ok else '<-- ECART'}")

        print("\n== CONGE ET PERMISSION : jours autorisés de l'année (une ligne à la fois) ==")
        for l in lire_tableau(wb, "Tableau4"):
            mat, svc = _txt(l["N° MATRICULE"]), _txt(l["SERVICE"])
            dep, ret = _date(l["DATE DE DEPART"]), _date(l["DATE DE RETOUR"])
            if not (mat and dep and ret):
                continue
            attendu = _num(l["ANNEE D'ABSENCE AUTORISE"])
            d0, d1 = max(dep, debut_an), min(ret - dt.timedelta(days=1), ref)
            annulee = (_txt(l["ANNULATION"]) or "").upper().startswith("ANNUL")   # Excel laisse la cellule vide
            obtenu = jours_ouvrables(d0, d1, feries) if (not annulee and ret.year >= ref.year and dep <= ref) else None
            if attendu is None and obtenu in (None, 0):
                continue
            ok = attendu == obtenu
            ecarts += not ok
            print(f"  {mat:9} {dep} -> {ret}  excel={attendu!s:<5} api={obtenu!s:<5} {'OK' if ok else '<-- ECART'}")

    print(f"\nÉcarts : {ecarts}")


if __name__ == "__main__":
    main()
